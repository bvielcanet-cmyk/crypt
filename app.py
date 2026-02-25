import streamlit as st
import ccxt
import google.generativeai as genai
import pandas as pd
import time
from supabase import create_client

# --- 1. CONFIGURATION SYSTÈME ---
st.set_page_config(page_title="Gemini Master OS v5.6", layout="wide", page_icon="🧠")

@st.cache_resource
def init_all():
    """Initialisation avec gestion rigoureuse des erreurs d'API"""
    try:
        # --- CONFIGURATION OKX ---
        # On utilise les secrets pour l'authentification
        exchange_config = {
            'apiKey': st.secrets["okx_api_key"],
            'secret': st.secrets["okx_api_secret"],
            'password': st.secrets["okx_api_passphrase"], # La Passphrase de l'API
            'enableRateLimit': True,
        }
        ex = ccxt.okx(exchange_config)
        
        # FORÇAGE MODE DÉMO (Sandbox)
        ex.set_sandbox_mode(True) 
        # Header spécifique exigé par OKX pour le simulé
        ex.headers = {'x-simulated-trading': '1'}

        # --- CONFIGURATION GEMINI ---
        genai.configure(api_key=st.secrets["gemini_key"])
        
        # Détection dynamique du modèle (évite l'erreur 404)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # On nettoie le nom (ex: 'models/gemini-1.5-flash' -> 'gemini-1.5-flash')
        target_model_name = models[0].split('/')[-1] if models else "gemini-1.5-flash"
        model = genai.GenerativeModel(target_model_name)

        # --- CONFIGURATION SUPABASE ---
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])

        return ex, model, sb, target_model_name
    except Exception as e:
        st.error(f"❌ Erreur critique d'initialisation : {str(e)}")
        return None, None, None, None

# Lancement des moteurs
exchange, gemini_model, supabase, active_model_name = init_all()

# --- 2. BARRE LATÉRALE (DASHBOARD) ---
with st.sidebar:
    st.header("🛠 Diagnostic Système")
    
    if exchange:
        st.write(f"🤖 IA active : **{active_model_name}**")
        if st.button("💰 Tester Connexion OKX", use_container_width=True):
            try:
                # Test simple de récupération de solde
                balance = exchange.fetch_balance()
                st.success("✅ Connexion OKX Démo établie !")
                st.metric("Solde USDT (Simulé)", f"{balance.get('total', {}).get('USDT', 0):.2f}")
            except Exception as e:
                st.error(f"❌ Erreur OKX : {e}")
                st.info("💡 Rappel : Vos clés doivent être créées dans l'onglet 'DÉMO' d'OKX.")
    
    st.divider()
    auto_refresh = st.toggle("🔄 Auto-Refresh (60s)")

# --- 3. LOGIQUE DE SCAN ---
def run_crypto_analysis(symbol):
    try:
        # Récupération OHLCV (15 min, 50 bougies)
        bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        if not bars:
            return {"symbol": symbol, "error": "Pas de données reçues"}

        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        last_price = df['close'].iloc[-1]
        
        # Appel IA
        prompt = f"Analyse {symbol} à {last_price}$. Réponds uniquement 'BUY' ou 'WAIT' avec une raison de 3 mots."
        response = gemini_model.generate_content(prompt)
        
        return {
            "symbol": symbol, 
            "price": last_price, 
            "verdict": response.text.strip().upper(), 
            "df": df
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

# --- 4. INTERFACE PRINCIPALE ---
st.title("🛰️ Gemini Master OS v5.6")

if exchange:
    tab1, tab2 = st.tabs(["🔎 Scanner de Marché", "💼 Portefeuille Supabase"])

    with tab1:
        LISTE_CRYPTO = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'FET-USDT']
        
        if st.button("🚀 LANCER LE SCAN COMPLET", use_container_width=True):
            cols = st.columns(len(LISTE_CRYPTO))
            
            for i, symbol in enumerate(LISTE_CRYPTO):
                with cols[i]:
                    with st.spinner(f"Analyse {symbol}..."):
                        res = run_crypto_analysis(symbol)
                        
                        if "error" in res:
                            st.error(f"Erreur {symbol}")
                            st.caption(res["error"])
                        else:
                            st.metric(symbol, f"{res['price']}$")
                            
                            if "BUY" in res['verdict']:
                                st.success(res['verdict'])
                                # Bouton pour envoyer vers Supabase
                                if st.button(f"Confirmer {symbol}", key=f"btn_{symbol}"):
                                    supabase.table("positions").upsert({
                                        "symbol": symbol, 
                                        "entry_price": res['price'], 
                                        "stop_price": res['price'] * 0.98
                                    }).execute()
                                    st.toast("Position enregistrée !")
                            else:
                                st.info(res['verdict'])
                            
                            # Petit graphique
                            st.line_chart(res['df']['close'].tail(20), height=100)
                time.sleep(1) # Pause pour éviter le spam API

    with tab2:
        try:
            data = supabase.table("positions").select("*").execute()
            if data.data:
                df_pos = pd.DataFrame(data.data)
                st.dataframe(df_pos, use_container_width=True)
                if st.button("🗑️ Vider le portefeuille"):
                    supabase.table("positions").delete().neq("symbol", "TEMP").execute()
                    st.rerun()
            else:
                st.info("Aucune position ouverte.")
        except Exception as e:
            st.error(f"Erreur Supabase : {e}")

# --- 5. GESTION AUTO-REFRESH ---
if auto_refresh:
    time.sleep(60)
    st.rerun()
