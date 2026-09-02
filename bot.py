import ccxt
import time
import requests
import os
import pandas as pd
from flask import Flask
from threading import Thread


# --- CONFIG ---
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")

exchange = ccxt.binance()

# Keep alive for Replit
app = Flask("")


@app.route("/")
def home():
    return "Bot is Running - OB + FVG Final"


def run_flask():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    thread = Thread(target=run_flask, daemon=True)
    thread.start()


def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN / CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
            },
            timeout=20,
        )
    except Exception as error:
        print(f"Telegram Error: {error}")


def calculate_adx(df, period=14):
    """Calculate Wilder's ADX without requiring an external TA package."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    upward_move = high.diff()
    downward_move = low.shift(1) - low
    positive_move = upward_move.where(
        (upward_move > downward_move) & (upward_move > 0),
        0.0,
    )
    negative_move = downward_move.where(
        (downward_move > upward_move) & (downward_move > 0),
        0.0,
    )

    alpha = 1 / period
    average_true_range = true_range.ewm(
        alpha=alpha,
        adjust=False,
        min_periods=period,
    ).mean()
    average_positive_move = positive_move.ewm(
        alpha=alpha,
        adjust=False,
        min_periods=period,
    ).mean()
    average_negative_move = negative_move.ewm(
        alpha=alpha,
        adjust=False,
        min_periods=period,
    ).mean()

    positive_di = 100 * average_positive_move / average_true_range
    negative_di = 100 * average_negative_move / average_true_range
    di_sum = positive_di + negative_di
    directional_index = (
        100
        * (positive_di - negative_di).abs()
        / di_sum.where(di_sum != 0)
    )

    return directional_index.ewm(
        alpha=alpha,
        adjust=False,
        min_periods=period,
    ).mean()


# --- NEW LOGIC: ORDER BLOCK + FVG ---
def check_ob_fvg(df):
    last_3 = df.tail(3)
    if len(last_3) < 3:
        return False, None, None

    # Bullish FVG: low of 3rd candle > high of 1st candle
    bullish_fvg = last_3["low"].iloc[2] > last_3["high"].iloc[0]

    # Bearish FVG: high of 3rd candle < low of 1st candle
    bearish_fvg = last_3["high"].iloc[2] < last_3["low"].iloc[0]

    # Order Block: bearish candle followed by bullish candle
    ob_bull = (
        df["close"].iloc[-2] < df["open"].iloc[-2]
        and df["close"].iloc[-1] > df["open"].iloc[-1]
    )
    ob_bear = (
        df["close"].iloc[-2] > df["open"].iloc[-2]
        and df["close"].iloc[-1] < df["open"].iloc[-1]
    )

    if bullish_fvg and ob_bull:
        zone = f"{last_3['high'].iloc[0]:.2f} - {last_3['low'].iloc[2]:.2f}"
        return True, "BULLISH", zone

    if bearish_fvg and ob_bear:
        zone = f"{last_3['low'].iloc[0]:.2f} - {last_3['high'].iloc[2]:.2f}"
        return True, "BEARISH", zone

    return False, None, None


def scan():
    symbols = [
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT",
        "BNB/USDT",
        "XRP/USDT",
        "ADA/USDT",
    ]

    print("Scanning started...")

    for symbol in symbols:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, "4h", limit=250)
            df = pd.DataFrame(
                ohlcv,
                columns=["time", "open", "high", "low", "close", "vol"],
            )

            df["EMA50"] = df["close"].ewm(span=50).mean()
            df["EMA200"] = df["close"].ewm(span=200).mean()
            df["ADX"] = calculate_adx(df)

            if (
                pd.isna(df["EMA50"].iloc[-1])
                or pd.isna(df["EMA200"].iloc[-1])
                or pd.isna(df["ADX"].iloc[-1])
            ):
                continue

            ema_cross_bull = (
                df["EMA50"].iloc[-2] < df["EMA200"].iloc[-2]
                and df["EMA50"].iloc[-1] > df["EMA200"].iloc[-1]
            )
            ema_cross_bear = (
                df["EMA50"].iloc[-2] > df["EMA200"].iloc[-2]
                and df["EMA50"].iloc[-1] < df["EMA200"].iloc[-1]
            )

            if (ema_cross_bull or ema_cross_bear) and df["ADX"].iloc[-1] > 22:
                has_signal, direction, zone = check_ob_fvg(df)

                if has_signal:
                    emoji = "🟢" if direction == "BULLISH" else "🔴"
                    trend = "EMA 50 Crossed 200 (4H)"
                    message = (
                        f"*{symbol} - SWING {direction} {emoji}*\n"
                        f"Trend: {trend}\n"
                        f"ADX: {df['ADX'].iloc[-1]:.1f}\n"
                        f"Entry Zone: {zone} (OB + FVG)\n"
                        "Chart: "
                        "https://www.tradingview.com/chart/?symbol="
                        f"BINANCE:{symbol.replace('/', '')}"
                    )
                    send_telegram(message)
                    print(f"Signal sent: {symbol} {direction}")

        except Exception as error:
            print(f"Error {symbol}: {error}")

    print("Scan Done")


# --- MAIN LOOP ---
if __name__ == "__main__":
    keep_alive()
    send_telegram("Bot Started: EMA 50/200 + ADX + OB + FVG Active ✅")

    while True:
        scan()
        time.sleep(14400)