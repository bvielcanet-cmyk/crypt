import streamlit as st
import ccxt
import google.generativeai as genai
import pandas as pd
import time
from supabase import create_client

st.set_page_config(page_title="Gemini Master OS v5.8", layout="wide")

@st.cache_resource
def init_all():
    # Initialisation de base
    genai.configure(api_key=st.secrets["gemini_key"])
    # Détection IA
    m_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target_ia = m_list[0].split('/')[-1] if m_list else "gemini-1.5-flash"
    ia_model = genai.GenerativeModel(target_ia)
    
    # Supabase
    sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])
    
    return ia_model, sb, target_ia

ia_engine, supabase, ia_name = init_all()

# --- SIDEBAR DE DIAGNOSTIC CRITIQUE ---
with st.sidebar:
    st.header("🔍 Audit de Connexion")
    
    # On récupère les clés une seule fois
    api_k = st.secrets["okx_api_key"]
    api_s = st.secrets["okx_api_secret"]
    api_p = st.secrets["okx_api_passphrase"]

    if st.button("⚡ TESTER : MODE DÉMO"):
        try:
            ex = ccxt.okx({'apiKey': api_k, 'secret': api_s, 'password': api_p})
            ex.set_sandbox_mode(True)
            ex.headers = {'x-simulated-trading': '1'}
            bal = ex.fetch_balance()
            st.success("✅ Tes clés sont bien des clés DÉMO !")
        except Exception as e:
            st.error(f"Échec Démo : {e}")

    if st.button("🛡️ TESTER : MODE RÉEL"):
        try:
            ex = ccxt.okx({'apiKey': api_k, 'secret': api_s, 'password': api_p})
            ex.set_sandbox_mode(False)
            bal = ex.fetch_balance()
            st.success("✅ Tes clés sont des clés RÉELLES (Live) !")
        except Exception as e:
            st.error(f"Échec Réel : {e}")

    st.divider()
    st.warning("Si les deux tests échouent avec l'erreur 50119, c'est que la clé n'existe pas ou que la Passphrase est fausse.")

# --- FONCTION DE RÉCUPÉRATION (SANS CRASH) ---
def try_fetch(symbol):
    try:
        # On recrée l'objet ici pour le test
        ex = ccxt.okx({
            'apiKey': st.secrets["okx_api_key"],
            'secret': st.secrets["okx_api_secret"],
            'password': st.secrets["okx_api_passphrase"],
            'enableRateLimit': True,
        })
        # ESSAYE DE CHANGER True/False ICI SELON LE RÉSULTAT DU TEST SIDEBAR
        ex.set_sandbox_mode(True) 
        ex.headers = {'x-simulated-trading': '1'}
        
        bars = ex.fetch_ohlcv(symbol, timeframe='15m', limit=20)
        df = pd.DataFrame(bars, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        price = df['c'].iloc[-1]
        
        resp = ia_engine.generate_content(f"Analyse {symbol} à {price}. Réponds BUY ou WAIT.")
        return {"s": symbol, "p": price, "v": resp.text.upper(), "df": df}
    except Exception as e:
        return {"s": symbol, "err": str(e)}

# --- INTERFACE ---
st.title("🛰️ Gemini Master OS v5.8")

if st.button("🚀 LANCER LE SCAN"):
    cols = st.columns(3)
    for i, s in enumerate(['BTC-USDT', 'ETH-USDT', 'SOL-USDT']):
        with cols[i]:
            res = try_fetch(s)
            if "err" in res:
                st.error(f"Erreur {res['s']}")
                st.caption(res['err'])
            else:
                st.metric(res['s'], f"{res['p']}$")
                st.info(res['v'])
                st.line_chart(res['df']['c'])
