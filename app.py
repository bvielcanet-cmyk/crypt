import streamlit as st
import ccxt
import time

# --- 1. NETTOYAGE RADICAL DES SECRETS ---
# On récupère les valeurs et on supprime TOUT espace ou saut de ligne caché
try:
    K = st.secrets["okx_api_key"].strip()
    S = st.secrets["okx_api_secret"].strip()
    P = st.secrets["okx_api_passphrase"].strip()
except Exception as e:
    st.error(f"Erreur de lecture des secrets : {e}")
    st.stop()

st.title("🛡️ Diagnostic Force OKX v6.3")

# --- 2. AFFICHAGE DE SÉCURITÉ (POUR TOI) ---
with st.expander("🔍 Vérification visuelle des secrets"):
    st.write(f"Début de la Clé : `{K[:8]}...` (Vérifie si ça correspond à ta nouvelle clé)")
    st.write(f"Longueur Passphrase : `{len(P)}` caractères")

# --- 3. TENTATIVE DE CONNEXION ---
if st.button("⚡ TENTER LA CONNEXION RÉELLE"):
    try:
        # On crée une instance propre, sans aucune option superflue
        ex = ccxt.okx({
            'apiKey': K,
            'secret': S,
            'password': P,
        })
        
        # TEST 1 : SANS SANDBOX (MODE RÉEL)
        ex.set_sandbox_mode(False)
        
        with st.spinner("Appel OKX..."):
            bal = ex.fetch_balance()
            st.success("🎉 ENFIN ! Connexion réussie au compte réel.")
            st.write(f"Ton compte est vivant. Solde total : {bal.get('total', {}).get('USDT', 0)} USDT")
            
    except Exception as e:
        st.error(f"L'erreur persiste : {e}")
        st.info("Si le début de la clé ci-dessus est correct, l'erreur 50119 signifie qu'OKX ne reconnaît pas la Passphrase.")
