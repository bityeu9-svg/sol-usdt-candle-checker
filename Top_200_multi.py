import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========== CẤU HÌNH ==========
VIETNAM_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
TELEGRAM_BOT_TOKEN = "8371675744:AAEGtu-477FoXe95zZzE5pSG8jbkwrtc7tg"
TELEGRAM_CHAT_ID = "1652088640"
TOP_SYMBOL_LIMIT = 200
RATE_PERCENT = 1

SYMBOLS = []
last_fetch_time = None

def send_telegram_alert(message, is_critical=False):
    try:
        prefix = "🚨 *CẢNH BÁO NGHIÊM TRỌNG* 🚨\n" if is_critical else "⚠️ *CẢNH BÁO* ⚠️\n"
        formatted_message = prefix + message
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": formatted_message,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
    except Exception as e:
        print(f"⚠️ Telegram alert error: {e}")

def fetch_top_symbols():
    try:
        print("🔁 Lấy danh sách top coin volume cao...")
        url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        futures_usdt = [x for x in data if x['symbol'].endswith("USDT") and not x['symbol'].endswith("BUSD")]
        sorted_by_volume = sorted(futures_usdt, key=lambda x: float(x['quoteVolume']), reverse=True)

        symbols = []
        for item in sorted_by_volume[:TOP_SYMBOL_LIMIT]:
            symbols.append({
                "symbol": item["symbol"],
                "candle_interval": "5m",
                "limit": 2
            })

        return symbols
    except Exception as e:
        send_telegram_alert(f"Lỗi lấy top coin:\n```{str(e)}```", is_critical=True)
        return []

def fetch_latest_candle(symbol_config):
    try:
        url = "https://fapi.binance.com/fapi/v1/klines"
        params = {
            "symbol": symbol_config["symbol"],
            "interval": symbol_config["candle_interval"],
            "limit": symbol_config["limit"]
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        candle = data[-1]
        return {
            "symbol": symbol_config["symbol"],
            "open_time": datetime.fromtimestamp(candle[0] / 1000).replace(tzinfo=ZoneInfo("UTC")),
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4])
        }
    except Exception as e:
        print(f"❌ Lỗi lấy nến {symbol_config['symbol']}: {e}")
        return None

def analyze_candle(candle):
    try:
        open_price = candle["open"]
        high_price = candle["high"]
        low_price = candle["low"]
        close_price = candle["close"]

        upper = high_price - max(open_price, close_price)
        upper_percent = (upper / max(open_price, close_price)) * 100 if max(open_price, close_price) > 0 else 0

        lower = min(open_price, close_price) - low_price
        lower_percent = (lower / low_price) * 100 if low_price > 0 else 0

        candle_type = "other"
        if lower_percent >= RATE_PERCENT:
            candle_type = "Râu nến dưới"
        elif upper_percent >= RATE_PERCENT:
            candle_type = "Râu nến trên"

        return {
            "symbol": candle["symbol"],
            "candle_type": candle_type,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "upper_wick_percent": round(upper_percent, 2),
            "lower_wick_percent": round(lower_percent, 2),
            "trend_direction": "LONG" if candle_type == "Râu nến dưới" else "SHORT" if candle_type == "Râu nến trên" else "-"
        }
    except Exception as e:
        send_telegram_alert(f"Lỗi phân tích nến:\n```{str(e)}```", is_critical=True)
        return None

def send_telegram_notification(analysis):
    if analysis["candle_type"] == "other":
        return

    msg = f"""
📊 *{analysis['symbol']} - Nến {analysis['candle_type'].upper()}* lúc {datetime.now(VIETNAM_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━
📈 Open: {analysis['open']:.8f}
📉 Close: {analysis['close']:.8f}
🔺 High: {analysis['high']:.8f}
🔻 Low: {analysis['low']:.8f}
━━━━━━━━━━━━━━
🔼 Râu trên: {analysis['upper_wick_percent']:.4f}%
🔽 Râu dưới: {analysis['lower_wick_percent']:.4f}%
🎯 Long/Short?: {analysis['trend_direction']}"""

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": msg,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
    except Exception as e:
        print(f"❌ Telegram error: {e}")

def should_refresh_symbols():
    global last_fetch_time
    return last_fetch_time is None or (datetime.now() - last_fetch_time) >= timedelta(hours=24)

def process_symbol(symbol_config):
    candle = fetch_latest_candle(symbol_config)
    if not candle:
        return
    candle["symbol"] = symbol_config["symbol"]
    analysis = analyze_candle(candle)
    if analysis:
        print(f"✔️ {symbol_config['symbol']} | {analysis['candle_type']} | Râu trên: {analysis['upper_wick_percent']:.2f}% | Râu dưới: {analysis['lower_wick_percent']:.2f}%")
        send_telegram_notification(analysis)

def main():
    global SYMBOLS, last_fetch_time

    print("🟢 Bot đang chạy...")

    while True:
        try:
            now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))

            if should_refresh_symbols():
                SYMBOLS = fetch_top_symbols()
                last_fetch_time = datetime.now()
                print(f"✅ Cập nhật SYMBOLS lúc {last_fetch_time}")

            if now_utc.minute % 5 == 0 and now_utc.second < 3:
                print(f"\n⏱ Kiểm tra lúc {datetime.now(VIETNAM_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}")
                with ThreadPoolExecutor(max_workers=20) as executor:
                    futures = [executor.submit(process_symbol, sym) for sym in SYMBOLS]
                    for future in as_completed(futures):
                        pass  # Đã xử lý bên trong process_symbol

                time.sleep(300 - now_utc.second % 60)
            else:
                time.sleep(1)
        except Exception as e:
            error_msg = f"LỖI VÒNG LẶP:\n{e}\n{traceback.format_exc()}"
            print(error_msg)
            send_telegram_alert(f"```{error_msg}```", is_critical=True)
            time.sleep(10)

if __name__ == "__main__":
    main()
