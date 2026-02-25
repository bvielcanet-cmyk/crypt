import streamlit as st
import ccxt.pro as ccxt
import google.generativeai as genai
import pandas as pd
import pandas_ta as ta
import asyncio
import time
from supabase import create_client

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Gemini Survival v5.3", layout="wide")

# --- 2. SIDEBAR (AFFICHÉE EN PREMIER) ---
with st.sidebar:
    st.header("🛠 Diagnostic")
    if "okx_api_key" not in st.secrets:
        st.error("❌ Secrets non configurés !")
    else:
        st.success("✅ Secrets détectés")
    
    st.divider()
    st.info("Si tout est 'Indisponible', vérifiez que votre compte OKX est bien en mode DEMO.")

# --- 3. INITIALISATION ---
@st.cache_resource
def init_all():
    try:
        # Initialisation OKX
        ex = ccxt.okx({
            'apiKey': st.secrets["okx_api_key"],
            'secret': st.secrets["okx_api_secret"],
            'password': st.secrets["okx_api_passphrase"],
            'enableRateLimit': True,
        })
        ex.set_sandbox_mode(True)
        # On force le header simulation
        ex.headers = {'x-simulated-trading': '1'}
        
        # Gemini
        genai.configure(api_key=st.secrets["gemini_key"])
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Supabase
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])
        
        return ex, model, sb
    except Exception as e:
        st.error(f"Erreur d'initialisation : {e}")
        return None, None, None

exchange, gemini_model, supabase = init_all()

# --- 4. ANALYSE (VERSION SIMPLE POUR STABILITÉ) ---
async def fetch_crypto(symbol):
    try:
        # On utilise une méthode plus simple pour éviter les blocages
        bars = await asyncio.to_thread(exchange.fetch_ohlcv, symbol, '15m', limit=50)
        if not bars:
            return {"symbol": symbol, "error": "Pas de données"}
            
        df = pd.DataFrame(bars, columns=['t','o','h','l','c','v'])
        price = df['c'].iloc[-1]
        
        # IA simplifiée
        prompt = f"Analyse courte {symbol} à {price}$. Réponds 'BUY' ou 'WAIT'."
        response = await asyncio.to_thread(gemini_model.generate_content, prompt)
        
        return {"symbol": symbol, "price": price, "verdict": response.text.upper(), "df": df}
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

# --- 5. INTERFACE ---
st.title("🛰️ Gemini Survival OS v5.3")

if exchange:
    tab1, tab2 = st.tabs(["🔎 Scan", "💼 Portefeuille"])

    with tab1:
        SYMBOLS = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'FET-USDT', 'SAND-USDT']
        
        if st.button("🚀 LANCER LE SCAN", use_container_width=True):
            cols = st.columns(len(SYMBOLS))
            for i, s in enumerate(SYMBOLS):
                with cols[i]:
                    with st.spinner(s):
                        res = asyncio.run(fetch_crypto(s))
                        if "error" in res:
                            st.error(f"{s}")
                            st.caption(f"Détail: {res['error']}")
                        else:
                            st.metric(s, f"{res['price']}$")
                            st.write(res['verdict'])
                            st.line_chart(res['df']['c'].tail(20), height=100)
                time.sleep(1) # Sécurité quota

    with tab2:
        st.write("Gestion des positions via Supabase")
        # (L'affichage Supabase reste identique)
else:
    st.error("L'application n'a pas pu se connecter aux APIs. Vérifiez vos clés.")
