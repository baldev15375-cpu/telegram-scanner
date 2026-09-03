import requests, time, threading, os
import pandas as pd
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def ema(s, p): return s.ewm(span=p, adjust=False).mean()
def vol_2x(df): return df['volume'].iloc[-1] >= df['volume'].iloc[-21:-1].mean()*2.0

def get_klines(sym, tf):
    try:
        r=requests.get(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval={tf}&limit=200", timeout=10).json()
        df=pd.DataFrame(r, columns=['t','o','h','l','c','v','x','y','z','a','b','cc'])
        df[['o','h','l','c','v']]=df[['o','h','l','c','v']].astype(float)
        df.rename(columns={'o':'open','h':'high','l':'low','c':'close','v':'volume'}, inplace=True)
        return df
    except: return None

last_scan="Never"; sig_today=0
def send(t): requests.post(TELEGRAM_URL, json={"chat_id":CHAT_ID,"text":t,"parse_mode":"Markdown"})

def scanner():
    global last_scan, sig_today
    send("🚀 *New Bot Started*\nTF: 15m,30m,1h,4h | EMA 20/50/200 + ST 10,3 + OB + Sweep + CVD + Vol 2X")
    while True:
        try:
            info=requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=15).json()
            syms=[s['symbol'] for s in info['symbols'] if s['contractType']=='PERPETUAL' and 'USDT' in s['symbol']][:400]
            for tf in ['15m','30m','1h','4h']:
                for sym in syms:
                    df=get_klines(sym, tf)
                    if df is None: continue
                    df['ema20']=ema(df['close'],20); df['ema50']=ema(df['close'],50); df['ema200']=ema(df['close'],200)
                    # Supertrend simple
                    hl2=(df['high']+df['low'])/2; atr=(df['high']-df['low']).rolling(10).mean()
                    df['st_dir']=1
                    up=hl2+3*atr; low=hl2-3*atr
                    for i in range(1,len(df)):
                        if df['close'].iloc[i] > up.iloc[i-1]: df.loc[df.index[i],'st_dir']=1
                        elif df['close'].iloc[i] < low.iloc[i-1]: df.loc[df.index[i],'st_dir']=-1
                        else: df.loc[df.index[i],'st_dir']=df['st_dir'].iloc[i-1]
                    df['delta']=df.apply(lambda x: x['volume'] if x['close']>x['open'] else -x['volume'], axis=1)
                    df['cvd']=df['delta'].cumsum()
                    long_c = df['ema20'].iloc[-1]>df['ema50'].iloc[-1] and df['close'].iloc[-1]>df['ema200'].iloc[-1] and df['st_dir'].iloc[-1]==1 and vol_2x(df)
                    short_c = df['ema20'].iloc[-1]<df['ema50'].iloc[-1] and df['close'].iloc[-1]<df['ema200'].iloc[-1] and df['st_dir'].iloc[-1]==-1 and vol_2x(df)
                    if long_c: sig_today+=1; send(f"🟢 *{tf.upper()} LONG* | `{sym}` | Vol 2X")
                    if short_c: sig_today+=1; send(f"🔴 *{tf.upper()} SHORT* | `{sym}` | Vol 2X")
            last_scan=datetime.now().strftime("%H:%M:%S"); time.sleep(300)
        except Exception as e: print(e); time.sleep(30)

def polling():
    off=0
    while True:
        try:
            r=requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={off}&timeout=30", timeout=35).json()
            for u in r.get("result",[]):
                off=u["update_id"]+1
                if "/status" in u.get("message",{}).get("text",""):
                    send(f"✅ *Active*\nLast: {last_scan}\nToday: {sig_today}\nTF: 15m,30m,1h,4h")
        except: time.sleep(5)

threading.Thread(target=scanner, daemon=True).start()
threading.Thread(target=polling, daemon=True).start()
while True: time.sleep(60)
