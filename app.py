import streamlit as st
import ccxt
import google.generativeai as genai
import pandas as pd
import time
from supabase import create_client

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Gemini Master OS v7.6", layout="wide")

@st.cache_resource
def init_all():
    try:
        # ON PASSE SUR KRAKEN (Beaucoup moins de restrictions sur le Cloud)
        ex = ccxt.kraken({'enableRateLimit': True})
        
        # GEMINI
        genai.configure(api_key=st.secrets["gemini_key"].strip())
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_ia = models[0].split('/')[-1] if models else "gemini-1.5-flash"
        model = genai.GenerativeModel(target_ia)

        # SUPABASE
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])

        return ex, model, sb, target_ia
    except Exception as e:
        st.error(f"Erreur d'initialisation : {e}")
        return None, None, None, None

exchange, gemini_model, supabase, active_model = init_all()

# --- 2. LOGIQUE D'ANALYSE ---
def run_analysis(symbol):
    try:
        # Kraken utilise des formats comme BTC/USDT ou BTC/USD
        bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=30)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        last_price = df['close'].iloc[-1]
        
        prompt = f"Analyse {symbol} à {last_price}$. Réponds 'BUY' ou 'WAIT' + 3 mots de raison."
        response = gemini_model.generate_content(prompt)
        
        return {"symbol": symbol, "price": last_price, "verdict": response.text.upper(), "df": df}
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

# --- 3. INTERFACE ---
st.title("🛰️ Gemini Master OS v7.6 (Multi-Cloud Bypass)")

if exchange:
    tab1, tab2 = st.tabs(["🔎 Scanner", "💼 Base Supabase"])

    with tab1:
        # Format Kraken : BTC/USDT
        LISTE = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        
        if st.button("🚀 LANCER LE SCAN SUR KRAKEN", use_container_width=True):
            cols = st.columns(3)
            for i, symbol in enumerate(LISTE):
                with cols[i]:
                    with st.spinner(f"Scan {symbol}..."):
                        res = run_analysis(symbol)
                        if "error" in res:
                            st.error(f"Erreur : {res['error']}")
                        else:
                            st.metric(symbol, f"{res['price']}$")
                            st.info(res['verdict'])
                            st.line_chart(res['df']['close'])
                            
                            # Enregistrement optionnel
                            if "BUY" in res['verdict']:
                                try:
                                    supabase.table("positions").upsert({"symbol": symbol, "entry_price": res['price']}).execute()
                                    st.toast("Cible enregistrée !")
                                except: pass
                time.sleep(1)

    with tab2:
        try:
            data = supabase.table("positions").select("*").execute()
            st.dataframe(pd.DataFrame(data.data))
        except:
            st.info("Aucune donnée.")
