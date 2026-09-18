import os, requests, time, json
import pandas as pd

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
STATE_FILE = "last_alerts.json"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ENAUSDT", "XRPUSDT", "DOGEUSDT"]

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def get_klines(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=100"
        data = requests.get(url).json()
        df = pd.DataFrame(data, columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","ig"])
        df["c"] = df["c"].astype(float)
        df["EMA20"] = df["c"].ewm(span=20).mean()
        df["EMA50"] = df["c"].ewm(span=50).mean()
        return df
    except:
        return None

try:
    with open(STATE_FILE, "r") as f:
        last_alerts = json.load(f)
except:
    last_alerts = {}

for symbol in SYMBOLS:
    df = get_klines(symbol)
    if df is None:
        continue

    prev = df.iloc[-3]
    curr = df.iloc[-2]

    curr_price = curr["c"]
    gap = abs(curr["EMA20"] - curr["EMA50"]) / curr["EMA50"] * 100

    direction = None
    if prev["EMA20"] < prev["EMA50"] and curr["EMA20"] > curr["EMA50"]:
        direction = "BULLISH"
    elif prev["EMA20"] > prev["EMA50"] and curr["EMA20"] < curr["EMA50"]:
        direction = "BEARISH"

    if direction:
        last = last_alerts.get(symbol, {})
        last_dir = last.get("dir")
        last_time = last.get("time", 0)

        should_send = False
        if last_dir!= direction:
            should_send = True
        elif time.time() - last_time > 3600:
            should_send = True

        if should_send:
            emoji = "📈" if direction == "BULLISH" else "📉"
            msg = f"""20-50 CROSSOVER ALERT (15m)

{emoji} {symbol}
20 EMA crossed 50 EMA ({direction})
Price: {curr_price}
Gap: {gap:.2f}%
TF: 15m LIVE
SUCCESSFUL CROSS"""

            send_telegram(msg)
            last_alerts[symbol] = {"dir": direction, "time": time.time()}

with open(STATE_FILE, "w") as f:
    json.dump(last_alerts, f)
