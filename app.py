import streamlit as st
import ccxt
import google.generativeai as genai
import pandas as pd
import time
from supabase import create_client

# --- 1. CONFIGURATION SYSTÈME ---
st.set_page_config(page_title="Gemini Master OS v5.7", layout="wide")

@st.cache_resource
def init_all():
    try:
        # --- CONFIGURATION OKX ---
        # Note : Change False par True ici si tu es SÛR d'avoir des clés démo
        USE_DEMO_MODE = True 

        ex = ccxt.okx({
            'apiKey': st.secrets["okx_api_key"],
            'secret': st.secrets["okx_api_secret"],
            'password': st.secrets["okx_api_passphrase"],
            'enableRateLimit': True,
        })
        
        if USE_DEMO_MODE:
            ex.set_sandbox_mode(True)
            ex.headers = {'x-simulated-trading': '1'}
        else:
            ex.set_sandbox_mode(False)

        # --- CONFIGURATION GEMINI ---
        genai.configure(api_key=st.secrets["gemini_key"])
        # Détection automatique du modèle
        model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = model_list[0].split('/')[-1] if model_list else "gemini-1.5-flash"
        model = genai.GenerativeModel(target)

        # --- CONFIGURATION SUPABASE ---
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])

        return ex, model, sb, target, USE_DEMO_MODE
    except Exception as e:
        st.error(f"Erreur d'initialisation : {e}")
        return None, None, None, None, None

exchange, gemini_model, supabase, active_model, is_demo = init_all()

# --- 2. BARRE LATÉRALE ---
with st.sidebar:
    st.header("🛠 Diagnostic")
    st.write(f"Mode : **{'DÉMO (Simulé)' if is_demo else 'RÉEL'}**")
    st.write(f"IA : `{active_model}`")
    
    if st.button("🧪 TESTER CONNEXION OKX"):
        try:
            bal = exchange.fetch_balance()
            st.success("✅ Connexion réussie !")
            st.write(f"Balance USDT : {bal.get('total', {}).get('USDT', 0)}")
        except Exception as e:
            st.error(f"❌ Erreur : {e}")
            st.info("Si l'erreur 50119 persiste, vos clés ne sont pas compatibles avec le mode choisi.")

# --- 3. LOGIQUE DE SCAN ---
def run_analysis(symbol):
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

# --- 4. INTERFACE ---
st.title("🛰️ Gemini Master OS v5.7")

if exchange:
    t1, t2 = st.tabs(["🔎 Scanner", "💼 Portefeuille"])
    
    with t1:
        if st.button("🚀 LANCER LE SCAN", use_container_width=True):
            cryptos = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']
            cols = st.columns(3)
            for i, s in enumerate(cryptos):
                with cols[i]:
                    res = run_analysis(s)
                    if "error" in res:
                        st.error(f"Erreur {s}")
                        st.caption(res["error"])
                    else:
                        st.metric(s, f"{res['price']}$")
                        st.success(res['verdict']) if "BUY" in res['verdict'] else st.info(res['verdict'])
                        st.line_chart(res['df']['close'].tail(20))
                    time.sleep(1)

    with t2:
        try:
            res = supabase.table("positions").select("*").execute()
            if res.data:
                st.table(res.data)
            else:
                st.info("Aucune position en base de données.")
        except:
            st.error("Impossible de lire Supabase.")
