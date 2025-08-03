import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import traceback

# ========== CẤU HÌNH ==========
VIETNAM_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
TELEGRAM_BOT_TOKEN = "8371675744:AAEGtu-477FoXe95zZzE5pSG8jbkwrtc7tg"
TELEGRAM_CHAT_ID = "1652088640"
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/XXXXXXX"  # Thay bằng webhook thực của bạn

# Danh sách cặp tiền theo dõi
SYMBOLS = {
    "BTC_USDT": {"binance_symbol": "BTCUSDT", "candle_interval": "5m", "limit": 2},
    "ETH_USDT": {"binance_symbol": "ETHUSDT", "candle_interval": "5m", "limit": 2},
    "SOL_USDT": {"binance_symbol": "SOLUSDT", "candle_interval": "5m", "limit": 2},
    "ETC_USDT": {"binance_symbol": "ETCUSDT", "candle_interval": "5m", "limit": 2},
    "TON_USDT": {"binance_symbol": "TONUSDT", "candle_interval": "5m", "limit": 2},
    "LTC_USDT": {"binance_symbol": "LTCUSDT", "candle_interval": "5m", "limit": 2}
}

def send_slack_alert(error_message, is_critical=False):
    """Gửi cảnh báo lỗi đến Slack"""
    try:
        payload = {
            "text": f"🚨 *{'CRITICAL' if is_critical else 'WARNING'} ERROR* 🚨",
            "attachments": [
                {
                    "color": "#ff0000" if is_critical else "#ffcc00",
                    "fields": [
                        {
                            "title": "Error Message",
                            "value": f"```{error_message}```",
                            "short": False
                        },
                        {
                            "title": "Timestamp",
                            "value": datetime.now(VIETNAM_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
                            "short": True
                        }
                    ]
                }
            ]
        }
        requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        print(f"⚠️ Không thể gửi cảnh báo Slack: {str(e)}")

def fetch_latest_candle(symbol, interval, limit):
    """Lấy dữ liệu nến từ Binance API"""
    try:
        url = "https://fapi.binance.com/fapi/v1/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        candle_data = response.json()
        latest_candle = candle_data[-1]
        
        return {
            "open_time": datetime.fromtimestamp(latest_candle[0]/1000).replace(tzinfo=ZoneInfo("UTC")),
            "open_price": float(latest_candle[1]),
            "high_price": float(latest_candle[2]),
            "low_price": float(latest_candle[3]),
            "close_price": float(latest_candle[4]),
            "volume": float(latest_candle[5])
        }
    except Exception as error:
        error_msg = f"Lỗi khi lấy dữ liệu {symbol}: {str(error)}"
        print(f"🚨 {error_msg}")
        send_slack_alert(error_msg)
        return None

def analyze_candle_pattern(candle):
    """Phân tích mẫu nến với công thức chính xác"""
    try:
        open_price = candle["open_price"]
        high_price = candle["high_price"]
        low_price = candle["low_price"]
        close_price = candle["close_price"]
        
        body_size = abs(close_price - open_price)
        total_range = high_price - low_price
        upper_wick = high_price - max(open_price, close_price)
        lower_wick = min(open_price, close_price) - low_price
        
        upper_wick_percentage = (upper_wick / max(open_price, close_price)) * 100
        lower_wick_percentage = (lower_wick / min(open_price, close_price)) * 100
        
        has_upper_wick = (upper_wick > 3 * body_size) and (upper_wick_percentage > 0.4)
        has_lower_wick = (lower_wick > 3 * body_size) and (lower_wick_percentage > 0.4)
        
        is_pin_bar = (
            (body_size <= total_range * 0.3) and
            (max(upper_wick, lower_wick) >= total_range * 0.7) and
            (((min(open_price, close_price) - low_price) / total_range < 0.2) or
             ((high_price - max(open_price, close_price)) / total_range < 0.2))
        )
        
        pin_bar_type = None
        if is_pin_bar:
            if upper_wick > lower_wick * 3:
                pin_bar_type = "BEARISH_PIN_BAR"
            elif lower_wick > upper_wick * 3:
                pin_bar_type = "BULLISH_PIN_BAR"
        
        pattern_type = None
        if has_upper_wick:
            pattern_type = "UPPER_WICK"
        elif has_lower_wick:
            pattern_type = "LOWER_WICK"
        elif pin_bar_type:
            pattern_type = pin_bar_type
            
        return {
            "pattern_type": pattern_type,
            "upper_wick_percentage": round(upper_wick_percentage, 2),
            "lower_wick_percentage": round(lower_wick_percentage, 2),
            "body_size": round(body_size, 4),
            "total_range": round(total_range, 4),
            "trend_direction": "TĂNG" if close_price > open_price else "GIẢM"
        }
    except Exception as error:
        error_msg = f"Lỗi phân tích nến: {str(error)}"
        print(f"🚨 {error_msg}")
        send_slack_alert(error_msg)
        return None

def send_telegram_notification(symbol, candle, analysis):
    """Gửi thông báo chi tiết qua Telegram"""
    try:
        candle_time = candle["open_time"].astimezone(VIETNAM_TIMEZONE).strftime("%H:%M:%S")
        
        pin_bar_info = ""
        if "PIN_BAR" in analysis.get("pattern_type", ""):
            pin_bar_info = f"\n🎯 Loại Pin Bar: {analysis['pattern_type'].split('_')[0]}"
        
        message = f"""
🔔 *{symbol.replace('_', '/')}* - {analysis['pattern_type']} lúc {candle_time}
📊 Xu hướng: {analysis['trend_direction']}
📈 Râu trên: {analysis['upper_wick_percentage']}%
📉 Râu dưới: {analysis['lower_wick_percentage']}%
📏 Biên độ: {analysis['total_range']} ({analysis['body_size']} thân nến)
{pin_bar_info}
💵 Giá: {candle['open_price']} → {candle['close_price']}
🔗 Biểu đồ: https://www.binance.com/en/futures/{symbol.replace('_', '')}"""
        
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
        send_slack_alert(error_msg)

def main():
    print("🟢 Khởi động trình theo dõi nến Binance Futures")
    print(f"⏱ Múi giờ: {VIETNAM_TIMEZONE}")
    print(f"📊 Danh sách cặp tiền: {', '.join(SYMBOLS.keys())}\n")
    
    try:
        while True:
            current_time = datetime.now(VIETNAM_TIMEZONE)
            
            if current_time.minute % 5 == 0 and current_time.second < 10:
                print(f"\n=== Kiểm tra lúc {current_time.strftime('%H:%M:%S')} ===")
                
                for symbol_name, config in SYMBOLS.items():
                    try:
                        candle_data = fetch_latest_candle(
                            config["binance_symbol"],
                            config["candle_interval"],
                            config["limit"]
                        )
                        
                        if not candle_data:
                            continue
                            
                        candle_data["open_time"] = candle_data["open_time"].astimezone(VIETNAM_TIMEZONE)
                        analysis_result = analyze_candle_pattern(candle_data)
                        
                        if not analysis_result:
                            continue
                            
                        if analysis_result["pattern_type"]:
                            print(f"✅ {symbol_name} - {analysis_result['pattern_type']}")
                            print(f"   Râu trên: {analysis_result['upper_wick_percentage']}%")
                            print(f"   Râu dưới: {analysis_result['lower_wick_percentage']}%")
                            print(f"   Biên độ: {analysis_result['total_range']}")
                            send_telegram_notification(symbol_name, candle_data, analysis_result)
                        else:
                            print(f"ℹ️ {symbol_name} - Nến thông thường")
                            print(f"   Râu trên: {analysis_result['upper_wick_percentage']}%")
                            print(f"   Râu dưới: {analysis_result['lower_wick_percentage']}%")
                    
                    except Exception as error:
                        error_msg = f"Lỗi xử lý {symbol_name}: {str(error)}\n{traceback.format_exc()}"
                        print(f"🚨 {error_msg}")
                        send_slack_alert(error_msg)
                
                time.sleep(300 - current_time.second % 60)
            else:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\n🛑 Dừng chương trình theo yêu cầu")
        send_slack_alert("Bot đã dừng theo yêu cầu người dùng (KeyboardInterrupt)")
    except Exception as critical_error:
        error_msg = f"LỖI NGHIÊM TRỌNG: {str(critical_error)}\n{traceback.format_exc()}"
        print(f"🚨🚨 {error_msg}")
        send_slack_alert(error_msg, is_critical=True)
    finally:
        print("🔴 Kết thúc chương trình")

if __name__ == "__main__":
    main()
