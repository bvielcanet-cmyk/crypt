import ccxt
import google.generativeai as genai
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image
from supabase import create_client
import os
import re

# --- CONFIGURATION VIA SECRETS GITHUB ---
GEMINI_KEY = os.getenv("GEMINI_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialisation
ex = ccxt.kraken({'enableRateLimit': True})
genai.configure(api_key=GEMINI_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Modèle IA
models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
model_name = next((m for m in models if "flash" in m), models[0])
model = genai.GenerativeModel(model_name)

TOP_15 = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT', 'NEAR/USDT', 'LINK/USDT', 'DOT/USDT', 'MATIC/USDT']

def run_worker():
    print("🚀 Démarrage du scan autonome...")
    
    # 1. Génération de l'image mosaïque (identique à ton code actuel)
    fig, axes = plt.subplots(2, 4, figsize=(15, 8)) # Format 8 cryptos pour le worker
    plt.style.use('dark_background')
    data_summary = ""
    
    for i, s in enumerate(TOP_15):
        ax = axes[i // 4, i % 4]
        try:
            bars = ex.fetch_ohlcv(s, timeframe='1h', limit=30)
            df = pd.DataFrame(bars, columns=['t','o','h','l','c','v'])
            price = df['c'].iloc[-1]
            ax.plot(df['c'], color='#00FFA3')
            ax.set_title(f"{s}:{price}$")
            ax.axis('off')
            data_summary += f"{s}:{price}$ "
        except: ax.axis('off')

    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=80)
    img = Image.open(buf)

    # 2. Analyse IA
    prompt = f"Analyse ces graphiques. Données: {data_summary}. Identifie les pépites avec un score de 0 à 100. Format: SYMBOLE | SCORE | ACTION"
    response = model.generate_content([prompt, img])
    report = response.text
    print(f"🤖 Verdict IA : \n{report}")

    # 3. Logique Paper Trading
    for line in report.split("\n"):
        if "|" in line:
            try:
                parts = line.split("|")
                sym = parts[0].strip()
                score = int(re.sub(r'\D', '', parts[1]))
                action = parts[2].strip()

                if score >= 85 and "BUY" in action.upper():
                    # Vérifier si déjà en cours
                    check = supabase.table("paper_portfolio").select("*").eq("symbol", sym).eq("status", "OPEN").execute()
                    if not check.data:
                        price_match = re.search(f"{sym}:(\\d+\\.?\\d*)", data_summary)
                        p = float(price_match.group(1)) if price_match else 0
                        
                        supabase.table("paper_portfolio").insert({
                            "symbol": sym, "entry_price": p, "status": "OPEN", "score": score
                        }).execute()
                        print(f"✅ ACHAT SIMULÉ : {sym}")
            except: continue

if __name__ == "__main__":
    run_worker()
