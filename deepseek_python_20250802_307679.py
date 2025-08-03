import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import time

# ========== CẤU HÌNH ==========
VIETNAM_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
TELEGRAM_BOT_TOKEN = "8371675744:AAEGtu-477FoXe95zZzE5pSG8jbkwrtc7tg"
TELEGRAM_CHAT_ID = "1652088640"

# Danh sách cặp tiền theo dõi
SYMBOLS = {
    "BTC_USDT": {"binance_symbol": "BTCUSDT", "candle_interval": "5m", "limit": 2},
    "ETH_USDT": {"binance_symbol": "ETHUSDT", "candle_interval": "5m", "limit": 2},
    "SOL_USDT": {"binance_symbol": "SOLUSDT", "candle_interval": "5m", "limit": 2},
    "ETC_USDT": {"binance_symbol": "ETCUSDT", "candle_interval": "5m", "limit": 2},
    "TON_USDT": {"binance_symbol": "TONUSDT", "candle_interval": "5m", "limit": 2},
    "LTC_USDT": {"binance_symbol": "LTCUSDT", "candle_interval": "5m", "limit": 2}
}

def fetch_latest_candle(symbol, interval, limit):
    """Lấy dữ liệu nến từ Binance API"""
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        candle_data = response.json()
        latest_candle = candle_data[-2]  # Nến đã đóng gần nhất
        
        return {
            "open_time": datetime.fromtimestamp(latest_candle[0]/1000).replace(tzinfo=ZoneInfo("UTC")),
            "open_price": float(latest_candle[1]),
            "high_price": float(latest_candle[2]),
            "low_price": float(latest_candle[3]),
            "close_price": float(latest_candle[4]),
            "volume": float(latest_candle[5])
        }
    except Exception as error:
        print(f"🚨 Lỗi khi lấy dữ liệu {symbol}: {str(error)}")
        return None

def analyze_candle_pattern(candle):
    """Phân tích mẫu nến với tên biến đầy đủ"""
    open_price = candle["open_price"]
    high_price = candle["high_price"]
    low_price = candle["low_price"]
    close_price = candle["close_price"]
    
    # Tính toán các đặc điểm nến
    body_size = abs(close_price - open_price)
    upper_wick_size = high_price - max(open_price, close_price)
    lower_wick_size = min(open_price, close_price) - low_price
    
    # Tính phần trăm râu nến
    upper_wick_percentage = (upper_wick_size / max(open_price, close_price)) * 100
    lower_wick_percentage = (lower_wick_size / low_price) * 100
    
    # Kiểm tra các điều kiện
    has_upper_wick_pattern = (upper_wick_size > 3 * body_size) and (upper_wick_percentage > 0.4)
    has_lower_wick_pattern = (lower_wick_size > 3 * body_size) and (lower_wick_percentage > 0.4)
    is_pin_bar_pattern = (max(upper_wick_size, lower_wick_size) / body_size >= 1.5) and (
        (upper_wick_percentage > 1.0 and lower_wick_percentage < 0.1) or 
        (lower_wick_percentage > 1.0 and upper_wick_percentage < 0.1)
    )
    
    # Xác định loại mẫu nến
    pattern_type = None
    if has_upper_wick_pattern:
        pattern_type = "UPPER_WICK"
    elif has_lower_wick_pattern:
        pattern_type = "LOWER_WICK"
    elif is_pin_bar_pattern:
        pattern_type = "PIN_BAR"
        
    return {
        "pattern_type": pattern_type,
        "upper_wick_percentage": round(upper_wick_percentage, 2),
        "lower_wick_percentage": round(lower_wick_percentage, 2),
        "body_size": round(body_size, 4),
        "trend_direction": "TĂNG" if close_price > open_price else "GIẢM"
    }

def send_telegram_notification(symbol, candle, analysis):
    """Gửi thông báo chi tiết qua Telegram"""
    candle_time = candle["open_time"].astimezone(VIETNAM_TIMEZONE).strftime("%H:%M:%S")
    
    message = f"""
🔔 *{symbol.replace('_', '/')}* - {analysis['pattern_type']} lúc {candle_time}
📊 Xu hướng: {analysis['trend_direction']}
📈 Râu trên: {analysis['upper_wick_percentage']}%
📉 Râu dưới: {analysis['lower_wick_percentage']}%
💵 Giá: {candle['open_price']} → {candle['close_price']}
🔷 Kích thước thân nến: {analysis['body_size']}
🔗 Biểu đồ: https://www.binance.com/en/futures/{symbol.replace('_', '')}"""
    
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            },
            timeout=5
        )
    except Exception as error:
        print(f"⚠️ Lỗi gửi Telegram: {str(error)}")

def main():
    print("🟢 Khởi động trình theo dõi nến Binance Futures")
    print(f"⏱ Múi giờ: {VIETNAM_TIMEZONE}")
    print(f"📊 Danh sách cặp tiền: {', '.join(SYMBOLS.keys())}\n")
    
    try:
        while True:
            current_time = datetime.now(VIETNAM_TIMEZONE)
            
            # Chạy vào đầu mỗi phút thứ 5
            if current_time.minute % 5 == 0 and current_time.second < 10:
                print(f"\n=== Kiểm tra lúc {current_time.strftime('%H:%M:%S')} ===")
                
                for symbol_name, config in SYMBOLS.items():
                    # Lấy dữ liệu nến
                    candle_data = fetch_latest_candle(
                        config["binance_symbol"],
                        config["candle_interval"],
                        config["limit"]
                    )
                    
                    if not candle_data:
                        continue
                        
                    # Phân tích nến
                    candle_data["open_time"] = candle_data["open_time"].astimezone(VIETNAM_TIMEZONE)
                    analysis_result = analyze_candle_pattern(candle_data)
                    
                    # Hiển thị kết quả
                    if analysis_result["pattern_type"]:
                        print(f"✅ {symbol_name} - {analysis_result['pattern_type']}")
                        print(f"   Râu trên: {analysis_result['upper_wick_percentage']}%")
                        print(f"   Râu dưới: {analysis_result['lower_wick_percentage']}%")
                        send_telegram_notification(symbol_name, candle_data, analysis_result)
                    else:
                        print(f"ℹ️ {symbol_name} - Nến thông thường")
                        print(f"   Râu trên: {analysis_result['upper_wick_percentage']}%")
                        print(f"   Râu dưới: {analysis_result['lower_wick_percentage']}%")
                        send_telegram_notification(symbol_name, candle_data, analysis_result)
                
                time.sleep(300 - current_time.second % 60)  # Đếm ngược chính xác
            else:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\n🛑 Dừng chương trình theo yêu cầu")
    except Exception as critical_error:
        print(f"🚨 Lỗi nghiêm trọng: {str(critical_error)}")

if __name__ == "__main__":
    main()
