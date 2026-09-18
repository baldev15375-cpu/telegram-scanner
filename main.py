import ccxt, pandas as pd, requests, os
from datetime import datetime
import pytz

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TF = "15m"
SYMBOLS = ["ENAUSDT","TIAUSDT","BTCUSDT","ETHUSDT"]

def send_msg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

exchange = ccxt.binance()
ist = pytz.timezone('Asia/Kolkata')

for symbol in SYMBOLS:
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TF, limit=100)
        df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])
        
        # LIVE EMA
        df['ema20'] = df['c'].ewm(span=20, adjust=False).mean()
        df['ema50'] = df['c'].ewm(span=50, adjust=False).mean()
        
        prev_20 = df['ema20'].iloc[-2]
        prev_50 = df['ema50'].iloc[-2]
        curr_20 = df['ema20'].iloc[-1]
        curr_50 = df['ema50'].iloc[-1]
        curr_price = df['c'].iloc[-1]
        
        time_now = datetime.now(ist).strftime("%I:%M %p, %d %b %y")

        # ਜਿੱਦਾਂ ਹੀ LIVE Cross ਹੋਵੇ
        if prev_20 < prev_50 and curr_20 > curr_50:
            msg = f"🔔 {symbol} | {TF}\n⚡ 20 EMA CROSSED ABOVE 50 EMA\n🕒 {time_now}\n💰 Price: ${curr_price:.4f}"
            send_msg(msg)
            
        if prev_20 > prev_50 and curr_20 < curr_50:
            msg = f"🔔 {symbol} | {TF}\n⚠️ 20 EMA CROSSED BELOW 50 EMA\n🕒 {time_now}\n💰 Price: ${curr_price:.4f}"
            send_msg(msg)
            
    except: pass
