import requests
import pandas as pd
import time
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_msg(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

symbols = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","TIAUSDT","ARBUSDT","OPUSDT","SUIUSDT","APTUSDT","NEARUSDT","WUSDT","ENAUSDT","JUPUSDT","RENDERUSDT","FETUSDT","WIFUSDT"]
found = []

for symbol in symbols:
    try:
        r = requests.get(f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=15m&limit=55", timeout=10).json()
        df = pd.DataFrame(r)
        close = df[4].astype(float)
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        curr_ema20 = ema20.iloc[-1]
        curr_ema50 = ema50.iloc[-1]
        prev_ema20 = ema20.iloc[-2]
        prev_ema50 = ema50.iloc[-2]
        curr_price = close.iloc[-1]
        gap_pct = abs(curr_ema20 - curr_ema50) / curr_price * 100

        if prev_ema20 < prev_ema50 and curr_ema20 > curr_ema50 and gap_pct > 0.05:
            found.append(f"🚀 {symbol}\n📈 20 EMA ne 50 nu UPAR Cross kita (BULLISH)\n💰 Price: {curr_price}\n📊 Gap: {gap_pct:.2f}%\n⏱️ TF: 15m LIVE\n✅ SUCCESSFUL CROSS")
        if prev_ema20 > prev_ema50 and curr_ema20 < curr_ema50 and gap_pct > 0.05:
            found.append(f"📉 {symbol}\n📉 20 EMA ne 50 nu THALLE Cross kita (BEARISH)\n💰 Price: {curr_price}\n📊 Gap: {gap_pct:.2f}%\n⏱️ TF: 15m LIVE\n✅ SUCCESSFUL CROSS")
    except:
        pass
    time.sleep(0.2)

if found:
    msg = "20-50 CROSSOVER ALERT (15m)\n\n" + "\n\n".join(found)
    send_msg(msg)
    print(msg)
else:
    print("No Crossover - 20-50 Scanner Running OK")
