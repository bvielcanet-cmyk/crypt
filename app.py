import streamlit as st
import ccxt.pro as ccxt
import google.generativeai as genai
import pandas as pd
import pandas_ta as ta
import asyncio
import time
from datetime import datetime
from supabase import create_client

# --- 1. CONFIGURATION SYSTÈME ---
st.set_page_config(page_title="Gemini Master OS v5.1", layout="wide", page_icon="🧠")

@st.cache_resource
def init_all():
    """Initialisation avec diagnostic des connexions"""
    status = {"okx": False, "gemini": False, "supabase": False}
    
    # Vérification présence des secrets
    required = ["okx_api_key", "okx_api_secret", "okx_api_passphrase", "gemini_key", "supabase_url", "supabase_key"]
    if not all(k in st.secrets for k in required):
        return None, None, None, None, status

    try:
        # OKX Demo Trading
        ex = ccxt.okx({
            'apiKey': st.secrets["okx_api_key"],
            'secret': st.secrets["okx_api_secret"],
            'password': st.secrets["okx_api_passphrase"],
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        ex.set_sandbox_mode(True)
        ex.headers = {'x-simulated-trading': '1'}
        status["okx"] = True

        # Gemini IA (Détection dynamique)
        genai.configure(api_key=st.secrets["gemini_key"])
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_model = next((m for m in available_models if "gemini-1.5-flash" in m), available_models[0])
        model = genai.GenerativeModel(target_model)
        status["gemini"] = True

        # Supabase
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])
        status["supabase"] = True

        return ex, model, sb, target_model, status
    except Exception as e:
        st.error(f"Erreur technique : {e}")
        return None, None, None, None, status

# Lancement de l'initialisation
exchange, gemini_model, supabase, active_model, conn_status = init_all()

# --- 2. BARRE LATÉRALE (DASHBOARD) ---
with st.sidebar:
    st.header("🛠 Diagnostic")
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"{'🟢' if conn_status['okx'] else '🔴'} OKX")
    c2.markdown(f"{'🟢' if conn_status['gemini'] else '🔴'} IA")
    c3.markdown(f"{'🟢' if conn_status['supabase'] else '🔴'} DB")
    
    st.divider()
    st.header("⚙️ Paramètres")
    trail_dist = st.slider("Trailing Stop (%)", 1.0, 5.0, 2.0)
    auto_refresh = st.toggle("🔄 Auto-Refresh (60s)")
    
    if st.button("💰 Solde USDT Démo"):
        try:
            bal = asyncio.run(exchange.fetch_balance())
            st.metric("Disponible", f"{bal['total']['USDT']:.2f} $")
        except:
            st.error("Lien OKX rompu")

# --- 3. LOGIQUE BASE DE DONNÉES ---
def db_load_positions():
    try:
        res = supabase.table("positions").select("*").execute()
        return {item['symbol']: item for item in res.data}
    except: return {}

def db_save_trade(symbol, price, stop):
    try:
        supabase.table("positions").upsert({
            "symbol": symbol, "entry_price": price, "highest_price": price, "stop_price": stop
        }).execute()
        st.toast(f"✅ {symbol} enregistré !")
    except Exception as e:
        st.error(f"Erreur DB : {e}")

# --- 4. ANALYSE ROBUSTE ---
async def analyze_market(symbol):
    try:
        bars = await exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        if not bars or len(bars) < 20:
            return {"symbol": symbol, "error": "Données insuffisantes"}
            
        df = pd.DataFrame(bars, columns=['t','o','h','l','c','v'])
        df['rsi'] = ta.rsi(df['close' if 'close' in df else 'c'], length=14)
        
        price = df['c'].iloc[-1]
        rsi_val = df['rsi'].iloc[-1]
        
        prompt = f"Expert. {symbol} à {price}$, RSI {rsi_val:.1f}. 'BUY' ou 'WAIT' + 3 mots."
        response = gemini_model.generate_content(prompt)
        return {"symbol": symbol, "price": price, "verdict": response.text.upper(), "df": df}
    except Exception as e:
        return {"symbol": symbol, "error": "Erreur technique"}

# --- 5. INTERFACE PRINCIPALE ---
st.title("🛰️ Gemini Master OS v5.1")

if not all(conn_status.values()):
    st.warning("⚠️ Système partiellement déconnecté. Vérifiez vos Secrets Streamlit.")

positions = db_load_positions()
tab1, tab2 = st.tabs(["🔎 Scanner Live", "💼 Portefeuille"])

with tab1:
    SYMBOLS = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'FET-USDT', 'SAND-USDT']
    if st.button("🚀 LANCER LE SCAN COMPLET", use_container_width=True):
        cols = st.columns(len(SYMBOLS))
        for i, s in enumerate(SYMBOLS):
            with cols[i]:
                with st.spinner(f"Scan {s}"):
                    res = asyncio.run(analyze_market(s))
                    if "error" in res:
                        st.error(f"{s}")
                        st.caption(res["error"])
                    else:
                        st.metric(res['symbol'], f"{res['price']}$")
                        if "BUY" in res['verdict']:
                            st.success(res['verdict'])
                            if st.button(f"Confirmer {s}", key=f"b_{s}"):
                                db_save_trade(s, res['price'], res['price'] * (1 - trail_dist/100))
                                st.rerun()
                        else:
                            st.info(res['verdict'])
                        st.line_chart(res['df']['c'].tail(20), height=100)
                time.sleep(1.2)

with tab2:
    if positions:
        for sym, data in positions.items():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.write(f"**{sym}** | Entrée : {data['entry_price']}$")
                c2.metric("Stop Loss", f"{data['stop_price']:.2f}$")
                if c3.button("Fermer", key=f"del_{sym}"):
                    supabase.table("positions").delete().eq("symbol", sym).execute()
                    st.rerun()
    else:
        st.info("Aucune position active en base de données.")

# Rafraîchissement automatique
if auto_refresh:
    time.sleep(60)
    st.rerun()
