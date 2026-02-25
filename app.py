import streamlit as st
import ccxt
import pandas as pd
import google.generativeai as genai
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image
from supabase import create_client
import re

# --- 1. INITIALISATION (Identique v10.1) ---
@st.cache_resource
def init_all():
    try:
        ex = ccxt.kraken({'enableRateLimit': True})
        genai.configure(api_key=st.secrets["gemini_key"].strip())
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = next((m for m in models if "flash" in m), models[0])
        model = genai.GenerativeModel(target)
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])
        return ex, model, sb, target
    except Exception as e:
        st.error(f"Erreur d'initialisation : {e}")
        return None, None, None, None

exchange, gemini_model, supabase, active_model = init_all()

# --- 2. GÉNÉRATION IMAGE (Identique v10.1) ---
def get_multi_charts_image(symbols):
    fig, axes = plt.subplots(3, 5, figsize=(15, 8))
    plt.style.use('dark_background')
    fig.patch.set_facecolor('#0E1117')
    data_summary = ""
    for i, s in enumerate(symbols):
        ax = axes[i // 5, i % 5]
        try:
            bars = exchange.fetch_ohlcv(s, timeframe='1h', limit=30)
            df = pd.DataFrame(bars, columns=['t','o','h','l','c','v'])
            price = df['c'].iloc[-1]
            ax.plot(df['c'], color='#00FFA3', linewidth=1.5)
            ax.set_title(f"{s.split('/')[0]}: {price}$", color='white', fontsize=10)
            ax.axis('off')
            data_summary += f"{s}:{price}$ "
        except: ax.axis('off')
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=80)
    plt.close()
    return Image.open(buf), data_summary

# --- 3. INTERFACE ---
st.title("🛰️ Vision Scanner 15 - Expert Advisory")

TOP_15 = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT', 'NEAR/USDT', 'LINK/USDT', 'DOT/USDT', 'MATIC/USDT', 'ADA/USDT', 'XRP/USDT', 'DOGE/USDT', 'LTC/USDT', 'UNI/USDT', 'ATOM/USDT', 'SHIB/USDT']

if st.button("🚀 SCANNER & GÉNÉRER LES AVIS", use_container_width=True):
    with st.spinner("Analyse visuelle et rédaction des avis..."):
        try:
            full_img, summary_text = get_multi_charts_image(TOP_15)
            st.image(full_img, use_container_width=True)
            
            # PROMPT : On demande explicitement un avis court pour la bulle contextuelle
            prompt = f"""
            Analyse ces 15 graphiques. Prix : {summary_text}
            Pour CHAQUE crypto, donne un avis d'expert ultra-court.
            
            FORMAT STRICT :
            [SYMBOLE] | [SCORE] | [ACTION] | [AVIS_BULLE]
            """
            
            response = gemini_model.generate_content([prompt, full_img])
            report = response.text
            
            st.subheader("🤖 Avis Contextuels par Actif")
            
            # --- CRÉATION DES BULLES ---
            lines = report.split("\n")
            cols = st.columns(3) # On affiche les avis sur 3 colonnes pour la lisibilité
            col_idx = 0
            
            for line in lines:
                if "|" in line and "SCORE" not in line.upper():
                    try:
                        parts = line.split("|")
                        sym = parts[0].strip()
                        score = int(re.sub(r'\D', '', parts[1]))
                        action = parts[2].strip()
                        avis = parts[3].strip()
                        
                        with cols[col_idx % 3]:
                            # Style de la bulle selon l'action
                            if "BUY" in action.upper() and score > 80:
                                st.success(f"**{sym}** ({score}%) \n\n {avis}")
                                # Enregistrement auto des pépites
                                supabase.table("positions").insert({"symbol": sym, "verdict": avis, "score": score}).execute()
                            elif "BUY" in action.upper():
                                st.info(f"**{sym}** ({score}%) \n\n {avis}")
                            else:
                                st.warning(f"**{sym}** ({score}%) \n\n {avis}")
                        col_idx += 1
                    except: continue
                    
        except Exception as e:
            st.error(f"Erreur : {e}")

# --- 4. HISTORIQUE ---
st.divider()
if st.checkbox("📂 Voir les pépites en base"):
    try:
        data = supabase.table("positions").select("*").order("created_at", desc=True).limit(5).execute()
        st.table(data.data)
    except: st.write("Base non connectée.")
