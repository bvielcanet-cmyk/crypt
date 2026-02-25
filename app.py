import streamlit as st
import ccxt
import google.generativeai as genai
import pandas as pd
import time
from supabase import create_client

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Gemini Master OS v6.1", layout="wide")

@st.cache_resource
def init_all():
    try:
        # CONFIGURATION OKX ULTRA-PRÉCISE
        # On utilise un dictionnaire de configuration pour forcer les paramètres
        exchange_id = 'okx'
        exchange_class = getattr(ccxt, exchange_id)
        
        ex = exchange_class({
            'apiKey': st.secrets["okx_api_key"].strip(),
            'secret': st.secrets["okx_api_secret"].strip(),
            'password': st.secrets["okx_api_passphrase"].strip(),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'brokerId': '12345678' # ID générique parfois requis
            }
        })
        
        # --- LE FIX CRITIQUE POUR OKX DEMO ---
        # On ne se contente pas du sandbox_mode, on force l'URL V5
        ex.urls['api']['rest'] = 'https://www.okx.com'
        ex.set_sandbox_mode(True) 
        
        # On s'assure que le header est bien une chaîne de caractères
        ex.headers = {
            'x-simulated-trading': '1',
            'Content-Type': 'application/json'
        }

        # IA & SUPABASE
        genai.configure(api_key=st.secrets["gemini_key"].strip())
        model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_ia = model_list[0].split('/')[-1] if model_list else "gemini-1.5-flash"
        model = genai.GenerativeModel(target_ia)
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])

        return ex, model, sb, target_ia
    except Exception as e:
        st.error(f"Erreur init : {e}")
        return None, None, None, None

exchange, gemini_model, supabase, active_model = init_all()

# --- 2. SIDEBAR DE DIAGNOSTIC ---
with st.sidebar:
    st.header("🛠 Diagnostic de Connexion")
    
    # AFFICHAGE DE TEST POUR VÉRIFIER LES SECRETS (MASQUÉ PARTIELLEMENT)
    if st.toggle("Afficher infos debug"):
        st.write(f"Clé: `{st.secrets['okx_api_key'][:5]}***`")
        st.write(f"Passphrase configurée: `{'✅' if st.secrets['okx_api_passphrase'] else '❌'}`")

    if st.button("🧪 TESTER AUTHENTIFICATION"):
        try:
            # On utilise une requête très légère qui ne demande pas de fonds
            response = exchange.privateGetAccountConfig()
            st.success("✅ CONNEXION OKX RÉUSSIE !")
            st.json(response['data'][0]['acctLv']) # Affiche le niveau de compte
        except Exception as e:
            st.error(f"Erreur d'auth : {e}")
            st.info("💡 Si 50119 apparaît encore : Essayez de désactiver le mode Sandbox sur OKX et de recréer une clé standard pour voir si le message change.")

# --- 3. LOGIQUE PRINCIPALE (RESTE INCHANGÉE) ---
st.title("🛰️ Gemini Master OS v6.1")
if st.button("🚀 SCANNER LE MARCHÉ"):
    # (Logique de scan identique aux versions précédentes)
    st.write("Lancement de l'analyse...")
