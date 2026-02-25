import streamlit as st
import ccxt.pro as ccxt
import google.generativeai as genai
import pandas as pd
import pandas_ta as ta
import asyncio
import time
from supabase import create_client

# --- CONFIGURATION ---
st.set_page_config(page_title="Gemini Turbo OS v5.2", layout="wide")

@st.cache_resource
def init_all():
    try:
        ex = ccxt.okx({
            'apiKey': st.secrets["okx_api_key"],
            'secret': st.secrets["okx_api_secret"],
            'password': st.secrets["okx_api_passphrase"],
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        ex.set_sandbox_mode(True)
        ex.headers = {'x-simulated-trading': '1'}
        
        genai.configure(api_key=st.secrets["gemini_key"])
        model = genai.GenerativeModel("gemini-1.5-flash")
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])
        
        return ex, model, sb
    except Exception as e:
        st.error(f"Erreur d'initialisation : {e}")
        return None, None, None

exchange, gemini_model, supabase = init_all()

# --- ANALYSE ASYNCHRONE (RAPIDE) ---
async def fetch_and_analyze(symbol):
    """Effectue le scan d'une crypto de façon isolée"""
    try:
        # Retry spécifique pour ETH
        for attempt in range(2):
            try:
                bars = await exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
                if bars: break
            except:
                if attempt == 1: return {"symbol": symbol, "error": "OKX Timeout"}
                await asyncio.sleep(1)

        df = pd.DataFrame(bars, columns=['t','o','h','l','c','v'])
        df['rsi'] = ta.rsi(df['c'], length=14)
        price, rsi = df['c'].iloc[-1], df['rsi'].iloc[-1]
        
        # IA - On demande une réponse ultra-courte pour gagner du temps
        prompt = f"Trader pro. {symbol} @ {price}, RSI {rsi:.1f}. Répond juste 'BUY' ou 'WAIT' + 1 mot."
        response = await asyncio.to_thread(gemini_model.generate_content, prompt)
        
        return {"symbol": symbol, "price": price, "verdict": response.text.upper(), "df": df}
    except Exception as e:
        return {"symbol": symbol, "error": "Erreur"}

async def run_full_scan(symbols):
    """Lance tous les scans en même temps"""
    tasks = [fetch_and_analyze(s) for s in symbols]
    return await asyncio.gather(*tasks)

# --- INTERFACE ---
st.title("⚡ Gemini Turbo-Scanner v5.2")

tab1, tab2 = st.tabs(["🔎 Scanner Rapide", "💼 Portefeuille"])

with tab1:
    SYMBOLS = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'FET-USDT', 'SAND-USDT']
    
    if st.button("🚀 LANCER LE SCAN PARALLÈLE (Gain de temps 80%)", use_container_width=True):
        start_time = time.time()
        
        with st.spinner("Analyse simultanée en cours..."):
            # On lance tout en parallèle
            results = asyncio.run(run_full_scan(SYMBOLS))
            
            cols = st.columns(len(results))
            for i, res in enumerate(results):
                with cols[i]:
                    if "error" in res:
                        st.error(f"{res['symbol']}\nIndisponible")
                    else:
                        st.metric(res['symbol'], f"{res['price']}$")
                        if "BUY" in res['verdict']:
                            st.success(res['verdict'])
                            if st.button(f"Confirmer {res['symbol']}", key=f"b_{res['symbol']}"):
                                supabase.table("positions").upsert({
                                    "symbol": res['symbol'], "entry_price": res['price'], "stop_price": res['price']*0.98
                                }).execute()
                                st.rerun()
                        else:
                            st.info(res['verdict'])
                        st.line_chart(res['df']['c'].tail(15), height=100)
        
        st.caption(f"Scan terminé en {time.time() - start_time:.1f} secondes.")

with tab2:
    try:
        res = supabase.table("positions").select("*").execute()
        if res.data:
            for d in res.data:
                st.write(f"✅ **{d['symbol']}** | Entrée : {d['entry_price']}$ | [Supprimer]")
        else:
            st.info("Aucune position active.")
    except:
        st.error("Erreur Supabase")
