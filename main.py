import requests, pandas as pd, os, time

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

COINS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","LINKUSDT","LTCUSDT","TRXUSDT","DOTUSDT","MATICUSDT","SHIBUSDT","BCHUSDT","NEARUSDT","UNIUSDT","APTUSDT","ARBUSDT","OPUSDT","RNDRUSDT","INJUSDT","FILUSDT","ETCUSDT","STXUSDT","IMXUSDT","SUIUSDT","TIAUSDT","SEIUSDT","PEPEUSDT"]

def send_msg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

def check_signal(symbol):
    try:
        url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=15m&limit=60"
        r = requests.get(url, timeout=10).json()
        if not isinstance(r, list): return None
        df = pd.DataFrame(r, columns=['t','o','h','l','c','v','a','b','c1','d','e','f'])
        df['c'] = df['c'].astype(float)
        ema20 = df['c'].ewm(span=20).mean()
        ema50 = df['c'].ewm(span=50).mean()
        
        # 20 ਨੇ 50 ਨੂੰ ਨੀਚੇ ਤੋਂ ਉੱਪਰ Cross ਕੀਤਾ
        if ema20.iloc[-2] < ema50.iloc[-2] and ema20.iloc[-1] > ema50.iloc[-1]:
            return f"🚀 *BULLISH 20-50 CROSS*\n`{symbol}` - 15m\nPrice: {df['c'].iloc[-1]}"
        # 20 ਨੇ 50 ਨੂੰ ਉੱਪਰੋਂ ਥੱਲੇ Cross ਕੀਤਾ
        if ema20.iloc[-2] > ema50.iloc[-2] and ema20.iloc[-1] < ema50.iloc[-1]:
            return f"🔻 *BEARISH 20-50 CROSS*\n`{symbol}` - 15m\nPrice: {df['c'].iloc[-1]}"
    except Exception as e:
        print(e)
    return None

signals = []
for coin in COINS:
    s = check_signal(coin)
    if s: signals.append(s)
    time.sleep(0.4)

if signals:
    for sig in signals:
        send_msg(sig)
else:
   else:
    send_msg(f"✅ 20-50 Scanner ON - {time.strftime('%d-%b %I:%M %p')} - 30 Coins Check - No Crossover")
    
