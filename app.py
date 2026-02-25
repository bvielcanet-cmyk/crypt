import streamlit as st
import ccxt
import google.generativeai as genai
import pandas as pd
import time
from supabase import create_client

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Gemini Master OS v6.0", layout="wide")

@st.cache_resource
def init_all():
    try:
        # Initialisation OKX avec paramètres de sécurité renforcés
        ex = ccxt.okx({
            'apiKey': st.secrets["okx_api_key"].strip(),
            'secret': st.secrets["okx_api_secret"].strip(),
            'password': st.secrets["okx_api_passphrase"].strip(),
            'enableRateLimit': True,
        })
        
        # FORÇAGE MANUEL DU SERVEUR DÉMO
        ex.set_sandbox_mode(True)
        # Certains systèmes exigent ce header précis pour le simulé
        ex.headers = {
            'x-simulated-trading': '1',
            'Content-Type': 'application/json'
        }

        # Configuration IA (Détection dynamique)
        genai.configure(api_key=st.secrets["gemini_key"].strip())
        model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_ia = model_list[0].split('/')[-1] if model_list else "gemini-1.5-flash"
        model = genai.GenerativeModel(target_ia)

        # Supabase
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])

        return ex, model, sb, target_ia
    except Exception as e:
        st.error(f"Erreur d'initialisation : {e}")
        return None, None, None, None

exchange, gemini_model, supabase, active_model = init_all()

# --- 2. BARRE LATÉRALE DE DIAGNOSTIC ---
with st.sidebar:
    st.header("🛠 Audit de Sécurité")
    
    if st.button("🔍 TESTER LA CLÉ MAINTENANT"):
        try:
            # On force un appel vers le compte démo
            balance = exchange.fetch_balance()
            st.success("✅ CONNEXION RÉUSSIE !")
            st.balloons()
            st.metric("Solde USDT Démo", f"{balance.get('total', {}).get('USDT', 0)}")
        except Exception as e:
            st.error(f"Erreur détectée : {e}")
            if "50119" in str(e):
                st.markdown("""
                **Vérification de survie (Erreur 50119) :**
                1. Allez sur OKX > API.
                2. Ta clé est-elle dans **'Trading démo'** ? (Si c'est 'V5 API', c'est l'erreur).
                3. Ta **Passphrase** dans Streamlit est-elle EXACTEMENT celle créée avec la clé ?
                4. As-tu cliqué sur **SAVE** en bas de la page Secrets de Streamlit ?
                """)

# --- 3. SCANNER ---
def run_scan(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=30)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        price = df['close'].iloc[-1]
        
        # IA
        prompt = f"Analyse {symbol} à {price}$. Réponds 'BUY' ou 'WAIT' + 2 mots."
        response = gemini_model.generate_content(prompt)
        
        return {"symbol": symbol, "price": price, "verdict": response.text.upper(), "df": df}
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

# --- 4. INTERFACE PRINCIPALE ---
st.title("🛰️ Gemini Master OS v6.0")

if exchange:
    if st.button("🚀 LANCER LE SCAN", use_container_width=True):
        cryptos = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']
        cols = st.columns(3)
        for i, s in enumerate(cryptos):
            with cols[i]:
                res = run_scan(s)
                if "error" in res:
                    st.error(f"Indisponible : {res['symbol']}")
                    st.caption(res['error'])
                else:
                    st.metric(s, f"{res['price']}$")
                    st.info(res['verdict'])
                    st.line_chart(res['df']['close'].tail(20))
                time.sleep(1)
