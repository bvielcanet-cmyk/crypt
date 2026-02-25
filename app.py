import streamlit as st
import ccxt
import google.generativeai as genai
import pandas as pd
import time
from supabase import create_client

# --- 1. CONFIGURATION SYSTÈME ---
st.set_page_config(page_title="Gemini Master OS v7.5", layout="wide", page_icon="🛰️")

@st.cache_resource
def init_all():
    try:
        # CONFIGURATION BINANCE PUBLIC (SANS CLÉS)
        # On utilise ccxt sans paramètres API pour le flux public
        ex = ccxt.binance({
            'enableRateLimit': True,
        })
        
        # CONFIGURATION GEMINI
        genai.configure(api_key=st.secrets["gemini_key"].strip())
        # Détection dynamique du modèle pour éviter l'erreur 404
        m_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_ia = m_list[0].split('/')[-1] if m_list else "gemini-1.5-flash"
        model = genai.GenerativeModel(target_ia)

        # CONFIGURATION SUPABASE
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])

        return ex, model, sb, target_ia
    except Exception as e:
        st.error(f"Erreur d'initialisation : {e}")
        return None, None, None, None

exchange, gemini_model, supabase, active_model = init_all()

# --- 2. LOGIQUE D'ANALYSE ---
def run_analysis(symbol):
    try:
        # Récupération des prix publics (Spot Binance)
        bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=30)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        last_price = df['close'].iloc[-1]
        
        # Appel à l'IA Gemini
        prompt = f"Analyse le graphique de {symbol} à {last_price}$. Réponds uniquement 'BUY' ou 'WAIT' avec une raison de 3 mots."
        response = gemini_model.generate_content(prompt)
        verdict = response.text.strip().upper()
        
        return {
            "symbol": symbol, 
            "price": last_price, 
            "verdict": verdict, 
            "df": df
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

# --- 3. INTERFACE PRINCIPALE ---
st.title("🛰️ Gemini Master OS v7.5 (Flux Public)")

if exchange:
    tab1, tab2 = st.tabs(["🔎 Scanner de Marché", "💼 Historique Supabase"])

    with tab1:
        # Liste des cryptos (Format Binance : BTC/USDT)
        LISTE_CRYPTO = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
        
        if st.button("🚀 LANCER LE SCAN (SANS CLÉ API)", use_container_width=True):
            cols = st.columns(len(LISTE_CRYPTO))
            
            for i, symbol in enumerate(LISTE_CRYPTO):
                with cols[i]:
                    with st.spinner(f"Analyse {symbol}..."):
                        res = run_analysis(symbol)
                        
                        if "error" in res:
                            st.error(f"Erreur sur {symbol}")
                            st.caption(res["error"])
                        else:
                            st.metric(symbol, f"{res['price']}$")
                            
                            if "BUY" in res['verdict']:
                                st.success(res['verdict'])
                                # Test d'enregistrement Supabase
                                try:
                                    supabase.table("positions").upsert({
                                        "symbol": symbol, 
                                        "entry_price": res['price']
                                    }).execute()
                                    st.toast(f"✅ {symbol} enregistré !")
                                except:
                                    st.warning("Position détectée mais Supabase déconnecté.")
                            else:
                                st.info(res['verdict'])
                            
                            st.line_chart(res['df']['close'].tail(20), height=150)
                time.sleep(0.5) # Anti-spam léger

    with tab2:
        try:
            data = supabase.table("positions").select("*").execute()
            if data.data:
                st.write("Dernières détections enregistrées :")
                st.dataframe(pd.DataFrame(data.data), use_container_width=True)
            else:
                st.info("Aucune donnée dans Supabase.")
        except Exception as e:
            st.error(f"Erreur Supabase : {e}")

# --- 4. PIED DE PAGE ---
st.divider()
st.caption(f"Connecté via Binance Public | IA : {active_model}")
