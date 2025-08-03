import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import time

# ========== CẤU HÌNH ==========
VIETNAM_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
TELEGRAM_BOT_TOKEN = "8371675744:AAEGtu-477FoXe95zZzE5pSG8jbkwrtc7tg"
TELEGRAM_CHAT_ID = "1652088640"

# Danh sách cặp tiền cần theo dõi
SYMBOLS = {
    "BTC_USDT": {"binance": "BTCUSDT", "interval": "5m", "limit": 2},
    "ETH_USDT": {"binance": "ETHUSDT", "interval": "5m", "limit": 2},
    "SOL_USDT": {"binance": "SOLUSDT", "interval": "5m", "limit": 2},
    "ETC_USDT": {"binance": "ETCUSDT", "interval": "5m", "limit": 2},
    "TON_USDT": {"binance": "TONUSDT", "interval": "5m", "limit": 2},
    "LTC_USDT": {"binance": "LTCUSDT", "interval": "5m", "limit": 2}
}

# ========== HÀM CHÍNH ==========
def get_latest_closed_candle_binance(symbol, interval, limit):
    """Lấy dữ liệu nến từ Binance Futures API"""
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        latest_closed = data[-2]
        
        return {
            "symbol": symbol,
            "time": datetime.fromtimestamp(latest_closed[0]/1000).replace(tzinfo=ZoneInfo("UTC")),
            "open": float(latest_closed[1]),
            "high": float(latest_closed[2]),
            "low": float(latest_closed[3]),
            "close": float(latest_closed[4])
        }
    except Exception as e:
        print(f"⚠️ Lỗi API {symbol}: {str(e)}")
        return None

def check_candle_pattern(candle):
    """Phát hiện nến đặc biệt với công thức chính xác"""
    open_, high, low, close = candle["open"], candle["high"], candle["low"], candle["close"]
    body = abs(close - open_)
    
    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low

    # Công thức đã được kiểm tra kỹ
    upper_condition = (upper_wick > 3 * body) and ((upper_wick / close) > 0.004)  # Chia cho giá đóng
    lower_condition = (lower_wick > 3 * body) and ((lower_wick / open_) > 0.004)  # Chia cho giá mở
    
    is_pin_bar = (
        (max(upper_wick, lower_wick) / body >= 1.5) and
        ((upper_wick * 100 > 100 and lower_wick * 100 < 10) or 
         (lower_wick * 100 > 100 and upper_wick * 100 < 10))
    )

    if upper_condition:
        return True, "upper_wick"
    elif lower_condition:
        return True, "lower_wick"
    elif is_pin_bar:
        return True, "pin_bar"
    return False, None

def send_telegram_alert(symbol, pattern, candle):
    """Gửi cảnh báo qua Telegram"""
    message = f"""🚨 *PHÁT HIỆN NẾN ĐẶC BIỆT* 🚨
• Cặp: {symbol.replace('_', '/')}
• Mẫu: {pattern.upper()}
• Thời gian: {candle['time'].strftime('%Y-%m-%d %H:%M:%S')}
• Mở/Đóng: {candle['open']} → {candle['close']}
• Cao/Thấp: {candle['high']} / {candle['low']}
• Biến động: {(abs(candle['close']-candle['open'])/candle['open'])*100:.2f}%"""
    
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
        timeout=5
    )

def process_symbol(symbol_key, symbol_config):
    """Xử lý từng cặp tiền"""
    candle = get_latest_closed_candle_binance(
        symbol_config["binance"],
        symbol_config["interval"],
        symbol_config["limit"]
    )
    
    if not candle:
        return

    # Chuyển timezone và định dạng
    candle["time"] = candle["time"].astimezone(VIETNAM_TIMEZONE)
    time_str = candle["time"].strftime('%H:%M:%S')
    
    # Kiểm tra pattern
    is_special, pattern = check_candle_pattern(candle)
    
    if is_special:
        print(f"✅ {symbol_key} - {pattern.upper()} lúc {time_str}")
        send_telegram_alert(symbol_key, pattern, candle)
    else:
        print(f"""ℹ️ {symbol_key} - Nến thường lúc {time_str}
   Mở: {candle['open']}
   Đóng: {candle['close']} ({(candle['close']/candle['open']-1)*100:.2f}%)
   Râu: ↑{candle['high']-max(candle['open'], candle['close']):.2f} 
        ↓{min(candle['open'], candle['close'])-candle['low']:.2f}""")

# ========== MAIN ==========
def main():
    print("🔔 Bắt đầu theo dõi nến 5m trên Binance")
    print(f"📊 Các cặp: {', '.join(SYMBOLS.keys())}")
    print(f"⏰ Timezone: {VIETNAM_TIMEZONE}\n")
    
    while True:
        now = datetime.now(VIETNAM_TIMEZONE)
        
        if now.minute % 5 == 0 and now.second < 10:  # Kiểm tra đầu mỗi 5 phút
            print(f"\n=== Chu kỳ kiểm tra {now.strftime('%H:%M:%S')} ===")
            for symbol_key, config in SYMBOLS.items():
                process_symbol(symbol_key, config)
            time.sleep(300 - now.second % 60)  # Chính xác 5 phút
        else:
            time.sleep(1)

if __name__ == "__main__":
    # Kiểm tra kết nối trước khi chạy
    try:
        requests.get("https://api.binance.com", timeout=5)
        main()
    except Exception as e:
        print(f"❌ Lỗi khởi động: {str(e)}")
