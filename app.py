import streamlit as st
import ccxt
import google.generativeai as genai
import pandas as pd
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Gemini Master OS v6.2", layout="wide")

@st.cache_resource
def init_all():
    # On prépare les accès IA (qui fonctionnent déjà normalement)
    try:
        genai.configure(api_key=st.secrets["gemini_key"].strip())
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_ia = models[0].split('/')[-1] if models else "gemini-1.5-flash"
        ia_model = genai.GenerativeModel(target_ia)
        return ia_model, target_ia
    except:
        return None, "Erreur IA"

ia_engine, ia_name = init_all()

# --- 2. FONCTION DE CONNEXION DYNAMIQUE (LE FIX) ---
def get_working_exchange():
    """Tente de connecter OKX en mode Démo, puis en mode Réel si échec"""
    keys = {
        'apiKey': st.secrets["okx_api_key"].strip(),
        'secret': st.secrets["okx_api_secret"].strip(),
        'password': st.secrets["okx_api_passphrase"].strip(),
        'enableRateLimit': True,
    }
    
    # Tentative 1 : Mode Démo Forcé
    try:
        ex_demo = ccxt.okx(keys)
        ex_demo.set_sandbox_mode(True)
        ex_demo.headers = {'x-simulated-trading': '1'}
        ex_demo.fetch_balance() # Test d'appel
        return ex_demo, "DÉMO"
    except Exception as e:
        error_demo = str(e)
        
        # Tentative 2 : Mode Réel (au cas où vos clés seraient 'Live')
        try:
            ex_real = ccxt.okx(keys)
            ex_real.set_sandbox_mode(False)
            ex_real.fetch_balance() # Test d'appel
            return ex_real, "RÉEL"
        except Exception as e2:
            return None, f"DÉMO: {error_demo} | RÉEL: {str(e2)}"

# --- 3. INTERFACE ---
st.title("🛰️ Gemini Master OS v6.2")

with st.sidebar:
    st.header("🛠 Statut Connexion")
    if st.button("🔄 TESTER TOUTES LES ROUTES"):
        res_ex, mode = get_working_exchange()
        if res_ex:
            st.success(f"✅ Connecté en mode {mode}")
            st.session_state['active_ex'] = res_ex
        else:
            st.error("❌ Aucune route ne fonctionne")
            st.write(mode) # Affiche les détails des deux erreurs

# --- 4. SCANNER SÉCURISÉ ---
if 'active_ex' in st.session_state:
    if st.button("🚀 LANCER LE SCAN SUR LE CANAL ACTIF"):
        ex = st.session_state['active_ex']
        try:
            # On test sur BTC
            bars = ex.fetch_ohlcv('BTC-USDT', timeframe='15m', limit=10)
            df = pd.DataFrame(bars, columns=['t','o','h','l','c','v'])
            st.metric("BTC-USDT", f"{df['c'].iloc[-1]} $")
            st.success("Flux de données opérationnel !")
        except Exception as e:
            st.error(f"Erreur de flux : {e}")
else:
    st.warning("Veuillez cliquer sur 'TESTER TOUTES LES ROUTES' dans la sidebar.")
