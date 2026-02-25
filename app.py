import streamlit as st
import ccxt
import google.generativeai as genai
import pandas as pd
import pandas_ta as ta
import time
from supabase import create_client

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Gemini Master OS v5.4", layout="wide")

# --- 2. INITIALISATION ---
@st.cache_resource
def init_all():
    try:
        # On utilise ccxt standard (plus stable que ccxt.pro pour le debug)
        ex = ccxt.okx({
            'apiKey': st.secrets["okx_api_key"],
            'secret': st.secrets["okx_api_secret"],
            'password': st.secrets["okx_api_passphrase"],
            'enableRateLimit': True,
        })
        ex.set_sandbox_mode(True) 
        ex.headers = {'x-simulated-trading': '1'}
        
        genai.configure(api_key=st.secrets["gemini_key"])
        model = genai.GenerativeModel("gemini-1.5-flash")
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])
        
        return ex, model, sb
    except Exception as e:
        st.error(f"Erreur init : {e}")
        return None, None, None

exchange, gemini_model, supabase = init_all()

# --- 3. ANALYSE SÉCURISÉE ---
def fetch_and_analyze(symbol):
    try:
        # Récupération des données
        bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        
        # Vérification si les données sont valides avant de créer le DataFrame
        if not isinstance(bars, list) or len(bars) == 0:
            return {"symbol": symbol, "error": "OKX n'a renvoyé aucune donnée."}

        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        price = df['close'].iloc[-1]
        
        # IA Decision
        prompt = f"Analyse {symbol} à {price}$. Réponds 'BUY' ou 'WAIT' + 1 raison."
        response = gemini_model.generate_content(prompt)
        
        return {"symbol": symbol, "price": price, "verdict": response.text.upper(), "df": df}
    except Exception as e:
        # ICI : On affiche l'erreur réelle d'OKX
        return {"symbol": symbol, "error": str(e)}

# --- 4. INTERFACE ---
st.title("🛰️ Gemini Master OS v5.4")

with st.sidebar:
    st.header("🛠 Diagnostic")
    if st.button("💰 Tester la connexion OKX"):
        try:
            bal = exchange.fetch_balance()
            st.success(f"Connecté ! Solde: {bal.get('total', {}).get('USDT', 0)} USDT")
        except Exception as e:
            st.error(f"Echec connexion : {e}")

if exchange:
    SYMBOLS = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'FET-USDT', 'SAND-USDT']
    
    if st.button("🚀 LANCER LE SCAN", use_container_width=True):
        cols = st.columns(len(SYMBOLS))
        for i, s in enumerate(SYMBOLS):
            with cols[i]:
                res = fetch_and_analyze(s)
                if "error" in res:
                    st.error(f"{s}")
                    st.caption(f"Erreur: {res['error']}")
                else:
                    st.metric(s, f"{res['price']}$")
                    st.write(res['verdict'])
                    st.line_chart(df['close'].tail(20), height=100)
                time.sleep(1)
