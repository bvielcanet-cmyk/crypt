import streamlit as st
import ccxt
import google.generativeai as genai
import pandas as pd
import time
from supabase import create_client

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Gemini Master OS v5.5", layout="wide")

@st.cache_resource
def init_all():
    try:
        # OKX - Configuration robuste
        ex = ccxt.okx({
            'apiKey': st.secrets["okx_api_key"],
            'secret': st.secrets["okx_api_secret"],
            'password': st.secrets["okx_api_passphrase"],
            'enableRateLimit': True,
        })
        # IMPORTANT: Force le mode démo seulement si tu as des clés démo. 
        # Si tes clés sont réelles, Streamlit affichera l'erreur 50119.
        ex.set_sandbox_mode(True) 
        ex.headers = {'x-simulated-trading': '1'}
        
        # GEMINI - Détection dynamique pour éviter l'erreur 404
        genai.configure(api_key=st.secrets["gemini_key"])
        
        # On cherche le premier modèle disponible qui supporte la génération
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_model = models[0].replace('models/', '') if models else "gemini-1.5-flash"
        
        model = genai.GenerativeModel(target_model)
        
        # Supabase
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])
        
        return ex, model, sb, target_model
    except Exception as e:
        st.error(f"Erreur d'initialisation : {e}")
        return None, None, None, None

exchange, gemini_model, supabase, active_model = init_all()

# --- 2. INTERFACE ---
st.title("🛰️ Gemini Master OS v5.5")

with st.sidebar:
    st.header("🛠 Diagnostic")
    st.info(f"Modèle IA utilisé : {active_model}")
    if st.button("💰 Tester Connexion OKX"):
        try:
            bal = exchange.fetch_balance()
            st.success("Connexion Réussie !")
        except Exception as e:
            st.error(f"Erreur : {e}")
            st.warning("Conseil : Vérifiez que vos clés sont bien des clés 'DEMO' sur OKX.")

# --- 3. SCANNER ---
def run_scan(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        df = pd.DataFrame(bars, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        price = df['c'].iloc[-1]
        
        # Analyse IA
        response = gemini_model.generate_content(f"Analyse {symbol} à {price}. Réponds BUY ou WAIT.")
        return {"symbol": symbol, "price": price, "verdict": response.text.upper(), "df": df}
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

if exchange:
    if st.button("🚀 LANCER LE SCAN", use_container_width=True):
        symbols = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']
        cols = st.columns(3)
        for i, s in enumerate(symbols):
            with cols[i]:
                res = run_scan(s)
                if "error" in res:
                    st.error(f"{s}: {res['error']}")
                else:
                    st.metric(s, f"{res['price']}$")
                    st.write(res['verdict'])
                    st.line_chart(res['df']['c'].tail(20))
                time.sleep(1)
