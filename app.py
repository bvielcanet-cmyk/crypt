import streamlit as st
import ccxt
import pandas as pd
import google.generativeai as genai
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image
from supabase import create_client
import re

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Gemini Vision v9.6", layout="wide", page_icon="👁️")

@st.cache_resource
def init_all():
    ex = ccxt.kraken({'enableRateLimit': True})
    genai.configure(api_key=st.secrets["gemini_key"].strip())
    # Utilisation de flash pour la rapidité d'analyse d'image
    model = genai.GenerativeModel('gemini-1.5-flash')
    sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])
    return ex, model, sb

exchange, gemini_model, supabase = init_all()

# --- 2. GÉNÉRATION DU GRAPHIQUE EXPERT ---
def get_expert_chart(df, symbol):
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 5))
    
    # Prix et Moyenne Mobile pour l'aide visuelle
    df['ema'] = df['c'].ewm(span=20, adjust=False).mean()
    
    ax.plot(df.index, df['c'], color='#00FFA3', label='Prix', linewidth=2, alpha=0.9)
    ax.plot(df.index, df['ema'], color='#FF3E8D', label='EMA 20', linestyle='--', linewidth=1.5)
    
    # Remplissage esthétique pour la structure
    ax.fill_between(df.index, df['c'], df['c'].min(), color='#00FFA3', alpha=0.05)
    
    ax.set_title(f"Chart Analyse : {symbol} (1H)", fontsize=14, color='white', pad=20)
    ax.axis('off') # On laisse l'IA juger la forme pure sans pollution d'axes
    
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=120)
    plt.close()
    return Image.open(buf)

# --- 3. INTERFACE ---
st.title("👁️ Analyseur Visionnaire Gemini")
st.write("Sélectionnez une cible pour une expertise visuelle et technique approfondie.")

# Liste étendue pour le choix unitaire
LISTE_CHOIX = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT', 'NEAR/USDT', 'LINK/USDT', 'DOT/USDT', 'MATIC/USDT']
target = st.selectbox("🎯 Actif à expertiser :", LISTE_CHOIX)

if st.button("🔍 LANCER L'EXPERTISE VISUELLE", use_container_width=True):
    with st.spinner(f"Analyse des patterns graphiques pour {target}..."):
        try:
            # Récupération des données
            bars = exchange.fetch_ohlcv(target, timeframe='1h', limit=60)
            df = pd.DataFrame(bars, columns=['t','o','h','l','c','v'])
            img = get_expert_chart(df, target)
            price = df['c'].iloc[-1]
            
            # Prompt de Vision Expert
            prompt = f"""
            Analyse ce graphique pour {target}. Le prix actuel est de {price}$.
            Regarde la courbe verte (Prix) par rapport à la ligne rose (EMA 20).
            
            1. Identifie la figure chartiste (ex: rebond, cassure, range, triangle).
            2. Donne un score de confiance de 0 à 100 pour un achat immédiat.
            3. Si le score est > 80, explique pourquoi c'est une 'Pépite'.
            
            FORMAT DE RÉPONSE :
            VERDICT : [BUY/WAIT/SELL]
            SCORE : [0-100]
            ANALYSE : [Ton expertise en 15 mots max]
            """
            
            # Appel Gemini Vision
            response = gemini_model.generate_content([prompt, img])
            full_res = response.text
            
            # Affichage
            col_chart, col_data = st.columns([2, 1])
            
            with col_chart:
                st.image(img, use_container_width=True, caption=f"Graphique envoyé à l'IA")
                
            with col_data:
                st.metric("Prix Actuel", f"{price} $")
                st.markdown("### 🤖 Résultat de l'IA")
                st.info(full_res)
                
                # Logique d'enregistrement (Score > 80)
                try:
                    # Extraction du score
                    score_match = re.search(r"SCORE\s*:\s*(\[?\d+\]?)", full_res.upper())
                    score_val = int(re.sub(r'\D', '', score_match.group(1))) if score_match else 0
                    
                    if score_val > 80 and "BUY" in full_res.upper():
                        supabase.table("positions").insert({
                            "symbol": target,
                            "entry_price": price,
                            "verdict": f"VISION_{score_val}: {full_res[:150]}"
                        }).execute()
                        st.success(f"💎 Pépite enregistrée ! Score: {score_val}")
                    else:
                        st.warning("Score insuffisant pour archivage (>80 requis).")
                except Exception as e:
                    st.caption(f"Erreur extraction score : {e}")
                    
        except Exception as e:
            st.error(f"Erreur technique : {e}")

# --- 4. HISTORIQUE ---
st.divider()
if st.checkbox("📂 Voir les dernières pépites visuelles (Supabase)"):
    try:
        data = supabase.table("positions").select("*").order("created_at", desc=True).limit(5).execute()
        st.dataframe(pd.DataFrame(data.data), use_container_width=True)
    except:
        st.write("Aucune donnée disponible.")
