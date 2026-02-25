import streamlit as st
import hmac
import base64
import requests
import datetime

# --- FONCTION DE SIGNATURE NATIVE OKX ---
def get_okx_time_direct(api_key, secret_key, passphrase):
    url = "https://www.okx.com/api/v5/account/config" # Requête simple
    timestamp = datetime.datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
    message = timestamp + 'GET' + '/api/v5/account/config'
    
    mac = hmac.new(bytes(secret_key, encoding='utf-8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    d_hash = mac.digest()
    signature = base64.b64encode(d_hash).decode('utf-8')

    headers = {
        'OK-ACCESS-KEY': api_key,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': passphrase,
        'Content-Type': 'application/json',
        'x-simulated-trading': '0' # On teste en mode REEL pour valider la clé
    }
    
    response = requests.get(url, headers=headers)
    return response.json()

st.title("🛰️ Diagnostic Manuel OKX")

if st.button("🔌 TENTER UNE CONNEXION SANS CCXT"):
    try:
        K = st.secrets["okx_api_key"].strip()
        S = st.secrets["okx_api_secret"].strip()
        P = st.secrets["okx_api_passphrase"].strip()
        
        result = get_okx_time_direct(K, S, P)
        
        if result.get("code") == "0":
            st.success("✅ INCROYABLE ! La connexion manuelle fonctionne.")
            st.write("Le problème vient donc de la bibliothèque CCXT.")
            st.json(result)
        else:
            st.error(f"OKX rejette toujours : {result.get('msg')}")
            st.write(f"Code erreur : {result.get('code')}")
            
    except Exception as e:
        st.error(f"Erreur système : {e}")

st.divider()
st.info("Si le code 50119 apparaît encore ici, connecte-toi à OKX, va dans ton profil > Sécurité, et vérifie si tu n'as pas activé le 'Whitelist IP pour API'.")
