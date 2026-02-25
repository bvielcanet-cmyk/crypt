import streamlit as st
import ccxt
import google.generativeai as genai
import pandas as pd
import time
from supabase import create_client

# --- 1. CONFIGURATION SYSTÈME ---
st.set_page_config(page_title="Gemini Master OS v5.9", layout="wide", page_icon="🧠")

# --- 2. FONCTION D'INITIALISATION SÉCURISÉE ---
@st.cache_resource
def init_all():
    """Initialisation avec retour d'état détaillé"""
    reports = []
    try:
        # Configuration OKX
        ex = ccxt.okx({
            'apiKey': st.secrets["okx_api_key"],
            'secret': st.secrets["okx_api_secret"],
            'password': st.secrets["okx_api_passphrase"], # Ta Passphrase API
            'enableRateLimit': True,
        })
        # Forçage Mode Démo
        ex.set_sandbox_mode(True)
        ex.headers = {'x-simulated-trading': '1'}
        reports.append("✅ Configuration OKX prête")

        # Configuration Gemini
        genai.configure(api_key=st.secrets["gemini_key"])
        model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_ia = model_list[0].split('/')[-1] if model_list else "gemini-1.5-flash"
        ia_model = genai.GenerativeModel(target_ia)
        reports.append(f"✅ IA connectée ({target_ia})")

        # Configuration Supabase
        sb = create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])
        reports.append("✅ Base de données connectée")

        return ex, ia_model, sb, reports
    except Exception as e:
        return None, None, None, [f"❌ Erreur : {str(e)}"]

# Lancement de l'initialisation
exchange, ia_engine, supabase, logs_init = init_all()

# --- 3. BARRE LATÉRALE DE DIAGNOSTIC ---
with st.sidebar:
    st.header("🔍 État des Services")
    for log in logs_init:
        st.write(log)
    
    st.divider()
    st.header("⚡ Test de Flux")
    if st.button("Vérifier Connexion OKX"):
        try:
            # Test d'appel réel à l'API
            balance = exchange.fetch_balance()
            st.success("Connexion OKX établie avec succès !")
            st.metric("Solde USDT Démo", f"{balance.get('total', {}).get('USDT', 0)}")
        except Exception as e:
            st.error(f"Erreur OKX : {e}")
            if "50119" in str(e):
                st.warning("CONSEIL : L'erreur 50119 indique que vos clés ne sont pas reconnues. Vérifiez votre PASSPHRASE et assurez-vous d'avoir créé les clés en MODE DÉMO.")

# --- 4. LOGIQUE DE SCAN ---
def run_scan(symbol):
    try:
        # Récupération des prix
        bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=30)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        price = df['close'].iloc[-1]
        
        # Analyse IA
        prompt = f"Analyse {symbol} à {price}$. Réponds uniquement 'BUY' ou 'WAIT' + 2 mots."
        response = ia_engine.generate_content(prompt)
        
        return {"symbol": symbol, "price": price, "verdict": response.text.upper(), "df": df}
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

# --- 5. INTERFACE PRINCIPALE ---
st.title("🛰️ Gemini Master OS v5.9")

if exchange:
    tab1, tab2 = st.tabs(["🔎 Scanner", "💼 Portefeuille"])
    
    with tab1:
        if st.button("🚀 LANCER LE SCAN COMPLET", use_container_width=True):
            cryptos = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']
            cols = st.columns(3)
            for i, s in enumerate(cryptos):
                with cols[i]:
                    with st.spinner(f"Analyse {s}..."):
                        res = run_scan(s)
                        if "error" in res:
                            st.error(f"Erreur {s}")
                            st.caption(res['error'])
                        else:
                            st.metric(s, f"{res['price']}$")
                            st.info(res['verdict'])
                            st.line_chart(res['df']['close'].tail(20))
                    time.sleep(1)

    with tab2:
        st.subheader("Positions en cours (Supabase)")
        try:
            data = supabase.table("positions").select("*").execute()
            if data.data:
                st.dataframe(data.data)
            else:
                st.info("Aucune position ouverte.")
        except:
            st.error("Impossible de charger les données Supabase.")
