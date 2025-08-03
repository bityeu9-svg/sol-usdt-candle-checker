import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import traceback

# ========== CẤU HÌNH ==========
VIETNAM_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
TELEGRAM_BOT_TOKEN = "8371675744:AAEGtu-477FoXe95zZzE5pSG8jbkwrtc7tg"
TELEGRAM_CHAT_ID = "1652088640"

# Chỉ theo dõi BTCUSDT
SYMBOLS = {
    "BTC_USDT": {"binance_symbol": "BTCUSDT", "candle_interval": "5m", "limit": 2}
}

def send_telegram_alert(message, is_critical=False):
    """Gửi cảnh báo đến Telegram"""
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
        print(f"⚠️ Lỗi khi gửi Telegram alert: {str(e)}")

def fetch_latest_candle(symbol_config):
    """Lấy dữ liệu nến từ Binance API"""
    try:
        url = "https://fapi.binance.com/fapi/v1/klines"
        params = {
            "symbol": symbol_config["binance_symbol"],
            "interval": symbol_config["candle_interval"],
            "limit": symbol_config["limit"]
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        candle_data = response.json()
        latest_candle = candle_data[-2]
        
        return {
            "open_time": datetime.fromtimestamp(latest_candle[0]/1000).replace(tzinfo=ZoneInfo("UTC")),
            "open": float(latest_candle[1]),
            "high": float(latest_candle[2]),
            "low": float(latest_candle[3]),
            "close": float(latest_candle[4])
        }
    except Exception as error:
        error_msg = f"Lỗi khi lấy dữ liệu BTCUSDT: {str(error)}"
        print(f"🚨 {error_msg}")
        send_telegram_alert(f"```{error_msg}```", is_critical=True)
        return None

def analyze_candle(candle):
    """Phân tích nến BTCUSDT"""
    try:
        open_price = candle["open"]
        high_price = candle["high"]
        low_price = candle["low"]
        close_price = candle["close"]
        
        body_size = abs(close_price - open_price)
        total_range = high_price - low_price
        
        lower_wick = min(open_price, close_price) - low_price
        lower_wick_percent = (lower_wick / low_price) * 100
        has_lower_wick = lower_wick_percent >= 0.29
        
        upper_wick = high_price - max(open_price, close_price)
        upper_wick_percent = (upper_wick / max(open_price, close_price)) * 100
        has_upper_wick = upper_wick_percent >= 0.22
        
        candle_type = "other"
        if has_lower_wick and not has_upper_wick:
            candle_type = "lower_wick"
        elif has_upper_wick and not has_lower_wick:
            candle_type = "upper_wick"
        
        return {
            "candle_type": candle_type,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "upper_wick_percent": round(upper_wick_percent, 4),
            "lower_wick_percent": round(lower_wick_percent, 4),
            "total_range_percent": round((total_range / low_price) * 100, 4),
            "trend_direction": "TĂNG" if close_price > open_price else "GIẢM"
        }
    except Exception as error:
        error_msg = f"Lỗi phân tích nến BTCUSDT: {str(error)}"
        print(f"🚨 {error_msg}")
        send_telegram_alert(f"```{error_msg}```", is_critical=True)
        return None

def send_telegram_notification(candle, analysis):
    """Gửi thông báo qua Telegram"""
    if analysis["candle_type"] == "other":
        return
    
    try:
        candle_time = candle["open_time"].astimezone(VIETNAM_TIMEZONE).strftime("%H:%M:%S")
        
        message = f"""
📊 *BTC/USDT - Nến {analysis['candle_type'].upper()}* lúc {candle_time}
━━━━━━━━━━━━━━
📈 Giá Mở: {analysis['open']:,.2f}
📉 Giá Đóng: {analysis['close']:,.2f}
🔺 Giá Cao: {analysis['high']:,.2f}
🔻 Giá Thấp: {analysis['low']:,.2f}
━━━━━━━━━━━━━━
📏 Biên độ: {analysis['total_range_percent']:.4f}%
🔼 Râu trên: {analysis['upper_wick_percent']:.4f}%
🔽 Râu dưới: {analysis['lower_wick_percent']:.4f}%
📊 Xu hướng: {analysis['trend_direction']}"""

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
        error_msg = f"Lỗi gửi Telegram: {str(error)}"
        print(f"🚨 {error_msg}")

def main():
    print("🟢 Khởi động trình theo dõi BTC/USDT")
    print(f"⏱ Múi giờ: {VIETNAM_TIMEZONE}")
    
    while True:
        try:
            now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
            
            if now_utc.minute % 5 == 0 and now_utc.second < 5:
                print(f"\n=== Kiểm tra lúc {now_utc.strftime('%H:%M:%S')} ===")
                
                candle_data = fetch_latest_candle(SYMBOLS["BTC_USDT"])
                
                if candle_data:
                    candle_data["open_time"] = candle_data["open_time"].astimezone(VIETNAM_TIMEZONE)
                    analysis_result = analyze_candle(candle_data)
                    
                    if analysis_result:
                        print(f"✅ BTC/USDT - Loại nến: {analysis_result['candle_type'].upper()}")
                        print(f"   Mở: {analysis_result['open']:,.2f} | Đóng: {analysis_result['close']:,.2f}")
                        print(f"   Cao: {analysis_result['high']:,.2f} | Thấp: {analysis_result['low']:,.2f}")
                        print(f"   Râu trên: {analysis_result['upper_wick_percent']:.4f}%")
                        print(f"   Râu dưới: {analysis_result['lower_wick_percent']:.4f}%")
                        
                        send_telegram_notification(candle_data, analysis_result)
                
                time.sleep(300 - now_utc.second % 60)
            else:
                time.sleep(1)
 
        except Exception as error:
            error_msg = f"LỖI: {str(error)}\n{traceback.format_exc()}"
            print(f"🚨🚨 {error_msg}")
            send_telegram_alert(f"```{error_msg}```", is_critical=True)
            time.sleep(10)  # Chờ 10s trước khi thử lại sau lỗi

if __name__ == "__main__":
    main()