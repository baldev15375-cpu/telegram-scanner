import json
import math
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import ccxt
import pandas as pd
import requests

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ.get("CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")

TIMEFRAME = "4h"
SYMBOL_LIMIT = 350
SCAN_INTERVAL_SECONDS = 1800
KLINE_LIMIT = 300
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 3
CHOP_PERIOD = 14
CHOP_THRESHOLD = 55
EMA_NEAR_THRESHOLD = 0.03
SIGNALS_FILE = Path("sent_signals.json")

exchange = ccxt.binance({"enableRateLimit": True})
IST = ZoneInfo("Asia/Kolkata")
stats_lock = threading.Lock()
last_scan_time = None
signals_today = 0
signals_today_date = None


def current_local_time():
    return datetime.now(IST)


def reset_daily_stats_if_needed():
    global signals_today, signals_today_date
    today = current_local_time().date()

    with stats_lock:
        if signals_today_date != today:
            signals_today = 0
            signals_today_date = today


def record_signal():
    global signals_today
    reset_daily_stats_if_needed()
    with stats_lock:
        signals_today += 1


def set_last_scan_time():
    global last_scan_time
    with stats_lock:
        last_scan_time = current_local_time()


def get_status_text():
    reset_daily_stats_if_needed()
    with stats_lock:
        scan_time = last_scan_time
        signal_count = signals_today

    formatted_scan_time = (
        scan_time.strftime("%Y-%m-%d %H:%M:%S IST")
        if scan_time
        else "Not completed yet"
    )
    return (
        "Scanner status:\n"
        "Supertrend 10,3 + EMA 50/200 + FVG + OB + "
        "Liquidity + CHOP active\n"
        "Scanning 350 pairs\n"
        f"Last scan time: {formatted_scan_time}\n"
        f"Total signals today: {signal_count}"
    )


def send_telegram(message, chat_id=None):
    target_chat_id = chat_id or CHAT_ID
    if not BOT_TOKEN or not target_chat_id:
        print("Missing BOT_TOKEN / CHAT_ID")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url,
            data={
                "chat_id": target_chat_id,
                "text": message,
            },
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()
        print(f"Telegram status: {response.status_code}")
        return bool(result.get("ok"))
    except Exception as error:
        print(f"Telegram error: {error}")
        return False


def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {
        "timeout": 30,
        "allowed_updates": json.dumps(["message"]),
    }
    if offset is not None:
        params["offset"] = offset

    response = requests.get(url, params=params, timeout=35)
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram getUpdates failed"))
    return result.get("result", [])


def handle_command(message):
    text = (message.get("text") or "").strip()
    if not text.startswith("/"):
        return

    command = text.split()[0].split("@")[0].lower()
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if chat_id is None:
        return

    if command == "/start":
        send_telegram(
            "Bot started. Scanner command handling is active.",
            chat_id=chat_id,
        )
    elif command == "/help":
        send_telegram(
            "/start - Start the bot\n"
            "/status - Show scanner status\n"
            "/help - Show available commands",
            chat_id=chat_id,
        )
    elif command == "/status":
        send_telegram(get_status_text(), chat_id=chat_id)


def telegram_polling_loop():
    offset = None
    while True:
        try:
            for update in get_updates(offset):
                offset = update["update_id"] + 1
                message = update.get("message")
                if message:
                    handle_command(message)
        except Exception as error:
            print(f"Telegram polling error: {error}")
            time.sleep(5)


def load_sent_signals():
    try:
        data = json.loads(SIGNALS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(str(item) for item in data)
    except FileNotFoundError:
        pass
    except (OSError, TypeError, ValueError) as error:
        print(f"Could not load duplicate filter state: {error}")
    return set()


def save_sent_signals(sent_signals):
    temporary_file = SIGNALS_FILE.with_suffix(".tmp")
    try:
        temporary_file.write_text(
            json.dumps(sorted(sent_signals), indent=2),
            encoding="utf-8",
        )
        temporary_file.replace(SIGNALS_FILE)
    except OSError as error:
        print(f"Could not save duplicate filter state: {error}")


def supertrend(df, period=SUPERTREND_PERIOD, multiplier=SUPERTREND_MULTIPLIER):
    hl2 = (df["high"] + df["low"]) / 2
    atr = (df["high"] - df["low"]).rolling(period).mean()
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr

    st_dir = [1]
    for index in range(1, len(df)):
        if df["close"].iloc[index] > upper.iloc[index - 1]:
            st_dir.append(1)
        elif df["close"].iloc[index] < lower.iloc[index - 1]:
            st_dir.append(-1)
        else:
            st_dir.append(st_dir[-1])

    result = df.copy()
    result["st"] = lower
    result["st_dir"] = st_dir
    return result


def choppiness_index(df, period=CHOP_PERIOD):
    previous_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - previous_close).abs(),
            (df["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    true_range_sum = true_range.rolling(period).sum()
    price_range = (
        df["high"].rolling(period).max()
        - df["low"].rolling(period).min()
    )
    ratio = (
        true_range_sum / price_range.replace(0, float("nan"))
    ).where(lambda values: values > 0)

    return ratio.map(
        lambda value: (
            100 * math.log10(value) / math.log10(period)
            if pd.notna(value) and value > 0
            else float("nan")
        )
    )


def find_next_order_block_target(closed_df, entry_high):
    start_index = len(closed_df) - 2
    minimum_index = max(1, len(closed_df) - 100)

    for index in range(start_index, minimum_index - 1, -1):
        bearish_candle = (
            closed_df["close"].iloc[index]
            < closed_df["open"].iloc[index]
        )
        bullish_follow_through = (
            closed_df["close"].iloc[index + 1]
            > closed_df["open"].iloc[index + 1]
        )

        if bearish_candle and bullish_follow_through:
            order_block_high = closed_df["high"].iloc[index]
            if order_block_high > entry_high:
                return float(order_block_high)

    return None


def get_usdt_symbols():
    markets = exchange.load_markets()
    symbols = [
        symbol
        for symbol, market in markets.items()
        if market.get("active", True)
        and market.get("quote") == "USDT"
        and market.get("spot", True)
    ]
    return sorted(symbols)[:SYMBOL_LIMIT]


def check(symbol):
    try:
        bars = exchange.fetch_ohlcv(
            symbol,
            TIMEFRAME,
            limit=KLINE_LIMIT,
        )
        if len(bars) < 210:
            return None

        df = pd.DataFrame(
            bars,
            columns=["time", "open", "high", "low", "close", "vol"],
        )
        df = supertrend(df)
        df["ema50"] = df["close"].ewm(span=50).mean()
        df["ema200"] = df["close"].ewm(span=200).mean()
        df["chop"] = choppiness_index(df)

        # Ignore the currently-forming candle.
        closed_df = df.iloc[:-1].copy()
        last = closed_df.iloc[-1]
        previous = closed_df.iloc[-2]
        fvg_reference = closed_df.iloc[-3]
        order_block = closed_df.iloc[-2]

        required_values = [
            last["st"],
            last["ema50"],
            last["ema200"],
            last["chop"],
        ]
        if any(pd.isna(value) for value in required_values):
            return None

        cond_supertrend = (
            previous["st_dir"] == -1
            and last["st_dir"] == 1
        )
        cond_ema = last["close"] > last["ema50"]
        cond_ema_near = (
            abs(last["ema50"] - last["ema200"])
            / last["ema200"]
            < EMA_NEAR_THRESHOLD
        )
        cond_chop = last["chop"] > CHOP_THRESHOLD
        cond_fvg = last["low"] > fvg_reference["high"]
        cond_order_block = (
            order_block["close"] < order_block["open"]
            and last["close"] > last["open"]
        )

        if not (
            cond_supertrend
            and cond_ema
            and cond_ema_near
            and cond_chop
            and cond_fvg
            and cond_order_block
        ):
            return None

        fvg_low = float(fvg_reference["high"])
        fvg_high = float(last["low"])
        ob_low = float(order_block["low"])
        ob_high = float(order_block["high"])
        entry_low = min(fvg_low, ob_low)
        entry_high = max(fvg_high, ob_high)

        supertrend_value = float(last["st"])
        stop_loss = supertrend_value * 0.995
        liquidity_high = float(
            closed_df["high"].rolling(50).max().iloc[-1]
        )
        next_order_block = find_next_order_block_target(
            closed_df,
            entry_high,
        )
        target_two = (
            next_order_block
            if next_order_block is not None
            else liquidity_high * 1.05
        )

        candle_time = int(last["time"])
        signal_key = f"{symbol}:LONG:{TIMEFRAME}:{candle_time}"

        return {
            "signal_key": signal_key,
            "symbol": symbol,
            "entry_low": entry_low,
            "entry_high": entry_high,
            "stop_loss": stop_loss,
            "liquidity_high": liquidity_high,
            "target_two": target_two,
            "chop": float(last["chop"]),
        }
    except Exception as error:
        print(f"{symbol} {error}")
        return None


def format_signal(signal):
    return (
        f"{signal['symbol']} LONG {TIMEFRAME}\n"
        f"ENTRY: {signal['entry_low']:.4f} - "
        f"{signal['entry_high']:.4f} (FVG + OB zone)\n"
        f"SL: {signal['stop_loss']:.4f} "
        f"(below SuperTrend {SUPERTREND_PERIOD},{SUPERTREND_MULTIPLIER})\n"
        f"T1: {signal['liquidity_high']:.4f} (Liquidity High)\n"
        f"T2: {signal['target_two']:.4f} (Next OB)\n"
        f"CHOP: {signal['chop']:.1f} (>{CHOP_THRESHOLD})"
    )


def scan_once(sent_signals):
    symbols = get_usdt_symbols()
    print(f"Scanning {len(symbols)} USDT pairs...")

    for symbol in symbols:
        signal = check(symbol)
        if not signal:
            time.sleep(0.5)
            continue

        signal_key = signal["signal_key"]
        if signal_key in sent_signals:
            print(f"Duplicate skipped: {symbol}")
            time.sleep(0.5)
            continue

        if send_telegram(format_signal(signal)):
            sent_signals.add(signal_key)
            save_sent_signals(sent_signals)
            record_signal()

        time.sleep(0.5)

    print("Scan Done")


def main():
    sent_signals = load_sent_signals()
    reset_daily_stats_if_needed()
    threading.Thread(
        target=telegram_polling_loop,
        name="telegram-polling",
        daemon=True,
    ).start()
    print(
        "Scanner started: Supertrend 10,3 + EMA 50/200 + "
        "FVG + OB + Liquidity + CHOP >55"
    )

    while True:
        try:
            scan_once(sent_signals)
        except Exception as error:
            print(f"Scanner error: {error}")
        finally:
            set_last_scan_time()
        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    import time
    from flask import Flask
    from threading import Thread

    app = Flask("")

    @app.route("/")
    def home():
        return "Bot is Alive"

    def run_web():
        app.run(host="0.0.0.0", port=8080)

    Thread(target=run_web).start()

    while True:
        try:
            print("Starting main bot loop...")
            main()
        except Exception as error:
            print(
                f"Bot crashed with error: {error}. "
                "Restarting in 10 seconds..."
            )
            time.sleep(10)