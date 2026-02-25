import streamlit as st
import ccxt
import pandas as pd
import google.generativeai as genai
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image
from supabase import create_client
import re
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Gemini Vision Scanner v10", layout="wide")

@st.cache_resource
def init_all():
    try:
        ex = ccxt.kraken({'enableRateLimit': True})
        genai.configure(api_key=st.secrets["gemini_key"].strip())
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = next((m for m in models if "flash" in m), models[0])
        model = genai.GenerativeModel(target)
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])
        return ex, model, sb
    except Exception as e:
        st.error(f"Erreur Init : {e}")
        return None, None, None

exchange, gemini_model, supabase = init_all()

# --- 2. GÉNÉRATION DE LA PLANCHE DE 15 GRAPHIQUES ---
def get_multi_charts_image(symbols):
    # On crée une grille de 5 colonnes x 3 lignes
    fig, axes = plt.subplots(3, 5, figsize=(20, 10))
    plt.style.use('dark_background')
    fig.patch.set_facecolor('#0E1117')
    
    data_summary = ""
    
    for i, s in enumerate(symbols):
        ax = axes[i // 5, i % 5]
        try:
            bars = exchange.fetch_ohlcv(s, timeframe='1h', limit=40)
            df = pd.DataFrame(bars, columns=['t','o','h','l','c','v'])
            price = df['c'].iloc[-1]
            
            # Dessin du mini-graphique
            ax.plot(df['c'], color='#00FFA3', linewidth=2)
            ax.set_title(f"{s}: {price}$", color='white', fontsize=12)
            ax.axis('off')
            
            data_summary += f"{s}:{price}$ | "
        except:
            ax.text(0.5, 0.5, "Erreur", color='red')
            ax.axis('off')

    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    plt.close()
    return Image.open(buf), data_summary

# --- 3. INTERFACE ---
st.title("🛰️ Vision Scanner 15 - Détecteur de Pépites")

TOP_15 = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT', 'NEAR/USDT',
    'LINK/USDT', 'DOT/USDT', 'MATIC/USDT', 'ADA/USDT', 'XRP/USDT',
    'DOGE/USDT', 'LTC/USDT', 'UNI/USDT', 'ATOM/USDT', 'SHIB/USDT'
]

if st.button("🚀 LANCER LE SCAN VISION DES 15 CRYPTOS", use_container_width=True):
    with st.spinner("Génération de la planche graphique et analyse IA..."):
        # 1. Création de l'image globale
        full_img, summary_text = get_multi_charts_image(TOP_15)
        
        # 2. Affichage de la planche pour l'utilisateur
        st.image(full_img, use_container_width=True, caption="Marché global analysé par l'IA")
        
        # 3. Prompt Vision pour analyse de groupe
        prompt = f"""
        Analyse cette planche de 15 graphiques. Données : {summary_text}
        
        MISSION :
        1. Repère LA pépite (celle avec la courbe la plus prometteuse).
        2. Donne un score de 0 à 100 pour chaque actif.
        
        FORMAT RÉPONSE :
        🎯 PÉPITE : [SYMBOLE]
        🔥 POURQUOI : [10 mots]
        
        LISTE :
        [SYMBOLE] | [SCORE] | [ACTION: BUY ou WAIT]
        """
        
        # 4. Appel IA
        response = gemini_model.generate_content([prompt, full_img])
        report = response.text
        
        st.markdown(f"### 🤖 Verdict du Scanner Vision\n{report}")
        
        # 5. Extraction et Enregistrement Supabase (Score > 80)
        lines = report.split("\n")
        for line in lines:
            if "|" in line:
                try:
                    parts = line.split("|")
                    sym = parts[0].strip()
                    score = int(re.sub(r'\D', '', parts[1]))
                    action = parts[2].strip()
                    
                    if score > 80 and "BUY" in action.upper():
                        supabase.table("positions").insert({
                            "symbol": sym,
                            "entry_price": 0, # Optionnel: récupérer le prix exact si besoin
                            "verdict": f"SCANNER_V10_SCORE_{score}"
                        }).execute()
                        st.toast(f"💎 {sym} enregistré (Score {score})")
                except: continue

st.divider()
if st.checkbox("📂 Voir l'historique Supabase"):
    try:
        hist = supabase.table("positions").select("*").order("created_at", desc=True).limit(10).execute()
        st.table(hist.data)
    except: st.write("Base vide.")
