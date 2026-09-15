import requests, pandas as pd, os, time

COINS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","LINKUSDT","LTCUSDT"]

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def check_signal(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=60"
    try:
        r = requests.get(url, timeout=10).json()
        if not isinstance(r, list):
            return None
        df = pd.DataFrame(r, columns=['t','o','h','l','c','v','a','b','c1','d','e','f'])
        df['c'] = df['c'].astype(float)
        ema20 = df['c'].ewm(span=20).mean()
        ema50 = df['c'].ewm(span=50).mean()
        if ema20.iloc[-2] < ema50.iloc[-2] and ema20.iloc[-1] > ema50.iloc[-1]:
            return f"BUY {symbol} 15m - 20 crossed ABOVE 50"
        if ema20.iloc[-2] > ema50.iloc[-2] and ema20.iloc[-1] < ema50.iloc[-1]:
            return f"SELL {symbol} 15m - 20 crossed BELOW 50"
    except:
        return None
    return None

for coin in COINS:
    sig = check_signal(coin)
    if sig:
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": sig})
        except:
            pass
        time.sleep(1)
