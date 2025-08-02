import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import json

# Cấu hình các cặp tiền cần theo dõi
SYMBOLS = {
    "SOL_USDT": {
        "binance": "SOLUSDT",
        "mexc": "SOL_USDT"
    },
    "BTC_USDT": {
        "binance": "BTCUSDT",
        "mexc": "BTC_USDT"
    },
    "ADA_USDT": {
        "binance": "ADAUSDT",
        "mexc": "ADA_USDT"
    },
    "TON_USDT": {
        "binance": "TONUSDT",
        "mexc": "TON_USDT"
    }
}

# -------- LẤY NẾN TỪ MEXC FUTURES --------
def get_latest_closed_candle(symbol="SOL_USDT", interval="5m", limit=2):
    url = "https://contract.mexc.com/api/v1/contract/kline"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()

    if not data.get("success"):
        raise Exception("Lỗi API Futures MEXC:", data)

    candles = data["data"]
    latest_closed = candles[-2]

    return {
        "symbol": symbol,
        "time": datetime.fromtimestamp(latest_closed["t"] / 1000).replace(tzinfo=ZoneInfo("UTC")),
        "open": float(latest_closed["o"]),
        "high": float(latest_closed["h"]),
        "low": float(latest_closed["l"]),
        "close": float(latest_closed["c"]),
    }

# -------- LẤY NẾN TỪ BINANCE FUTURES --------
def get_latest_closed_candle_binance(symbol="SOLUSDT", interval="5m", limit=2):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    latest_closed = data[-2]

    return {
        "symbol": symbol,
        "time": datetime.fromtimestamp(latest_closed[0] / 1000).replace(tzinfo=ZoneInfo("UTC")),
        "open": float(latest_closed[1]),
        "high": float(latest_closed[2]),
        "low": float(latest_closed[3]),
        "close": float(latest_closed[4]),
    }

# -------- KIỂM TRA MẪU NẾN --------
def has_long_wick_with_movement(candle, ratio_threshold=3.0, percent_threshold=0.4):
    open_, high, low, close = candle["open"], candle["high"], candle["low"], candle["close"]
    body = abs(close - open_)
    
    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low

    upper_condition = (
        upper_wick > ratio_threshold * body and 
        (upper_wick / max(open_, close)) > (percent_threshold / 100)
    )
    lower_condition = (
        lower_wick > ratio_threshold * body and 
        (lower_wick / low) > (percent_threshold / 100)
    )
    is_pin_bar = (
      max(upper_wick, upper_wick) / body >= 1.5 and # check thân nến so với râu nến phải mỏng
      ((upper_wick * 100 > 100 and lower_wick *  100 < 10 ) or (lower_wick * 100 > 100 and upper_wick * 100 < 10))
    )

    return upper_condition or lower_condition or is_pin_bar

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot8371675744:AAEGtu-477FoXe95zZzE5pSG8jbkwrtc7tg/sendMessage"
    payload = {
        "chat_id": 1652088640,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Lỗi gửi Telegram:", e)

def process_symbol(symbol_key):
    """Xử lý một cặp tiền cụ thể"""
    symbol_config = SYMBOLS[symbol_key]
    candle = None
    source = None

    # Ưu tiên lấy từ Binance
    try:
        candle = get_latest_closed_candle_binance(symbol=symbol_config["binance"])
        source = "Binance"
    except requests.exceptions.Timeout:
        print(f"⚠️ Timeout Binance cho {symbol_key}. Chuyển sang MEXC...")
        try:
            candle = get_latest_closed_candle(symbol=symbol_config["mexc"])
            source = "MEXC"
        except Exception as e:
            print(f"❌ MEXC cũng lỗi cho {symbol_key}:", e)
    except Exception as e:
        print(f"❌ Lỗi khác khi gọi Binance cho {symbol_key}:", e)

    if candle:
        candle_vn_time = candle["time"].astimezone(ZoneInfo("Asia/Bangkok"))
        if has_long_wick_with_movement(candle):
            print(f"✅ {symbol_key} - NẾN RÂU DÀI + DAO ĐỘNG > 0.5% tại {candle_vn_time.strftime('%Y-%m-%d %H:%M:%S')} (nguồn: {source})")
            message = f"""📊 *Phát Hiện Nến Râu Dài*
- Cặp: {symbol_key.replace('_', '/')}
- Thời gian: {candle_vn_time.strftime('%Y-%m-%d %H:%M:%S')}
- Giá mở: {candle['open']}
- Giá cao: {candle['high']}
- Giá thấp: {candle['low']}
- Giá đóng: {candle['close']}
- Nguồn: {source}"""
            send_telegram_message(message)
        else:
            print(f"❌ {symbol_key} - Nến không khớp mẫu.")

# -------- MAIN --------
def main():
    print("⏳ Đang theo dõi nến FUTURES 5m (Binance → fallback MEXC)...")
    print(f"📊 Các cặp đang theo dõi: {', '.join(SYMBOLS.keys())}\n")

    while True:
        now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
        now_vn = now_utc.astimezone(ZoneInfo("Asia/Bangkok"))

        if now_utc.minute % 5 == 0 and now_utc.second < 3:
            for symbol in SYMBOLS:
                process_symbol(symbol)
            time.sleep(300)  # Đợi 5 phút trước khi kiểm tra lại
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()