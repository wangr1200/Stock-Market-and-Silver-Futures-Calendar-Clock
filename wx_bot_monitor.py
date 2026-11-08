import time
import requests
import os
import json
import sys
import akshare as ak

# ================= 1. 配置区域 =================
SERVER_CHAN_KEY = "SCT464863Tfmh0nHqPb8JmYygfidSRGa2P"
CHECK_INTERVAL = 60  # 每 60 秒检查一次盘面

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".market_clock_cache")
ALERTS_FILE = os.path.join(CACHE_DIR, "price_alerts.json")

def load_alerts():
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] 读取预警文件失败: {e}")
    return []

def save_alerts(alerts):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(ALERTS_FILE, "w", encoding="utf-8") as f:
            json.dump(alerts, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 保存预警文件失败: {e}")

def send_wechat_notification(title, desp):
    url = f"https://sctapi.ftqq.com/{SERVER_CHAN_KEY}.send"
    data = {
        "title": title,
        "desp": desp
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("code") == 0:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [成功] 微信价格预警已成功推送到手机！")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] [异常] 发送微信消息失败: {e}")

def check_market_data():
    try:
        df = None
        try:
            df = ak.futures_zh_spot(symbol="AG0", market="SHFE")
        except Exception:
            pass

        if df is None or df.empty:
            try:
                df = ak.futures_zh_realtime(market="SHFE")
            except Exception:
                pass

        if df is None or df.empty:
            print(f"[{time.strftime('%H:%M:%S')}] 未能获取到行情数据...")
            return

        current_price = 0.0
        contract_desc = "沪银主力 (AG0)"

        for _, row in df.iterrows():
            try:
                row_str = str(row.values).upper()
                if 'AG' in row_str or '沪银' in row_str:
                    for col in ['trade', 'price', '最新价', '现价']:
                        if col in row and pd_notnull(row[col]):
                            try:
                                val = float(row[col])
                                if val > 0:
                                    current_price = val
                                    break
                            except:
                                pass
                    if current_price > 0:
                        break
            except Exception:
                continue

        if current_price == 0:
            try:
                df_main = ak.futures_main_sina()
                if df_main is not None and not df_main.empty:
                    for _, row in df_main.iterrows():
                        symbol = str(row.get('symbol', '')).username if hasattr(row.get('symbol', ''), 'username') else str(row.get('symbol', '')).upper()
                        name = str(row.get('name', ''))
                        if 'AG' in symbol or '银' in name:
                            current_price = float(row.get('trade', row.get('price', 0)))
                            contract_desc = f"{name} ({symbol})"
                            break
            except Exception:
                pass

        if current_price > 0:
            print(f"[{time.strftime('%H:%M:%S')}] 盯盘中 -> 合约: {contract_desc} | 当前最新价: {current_price}")

            alerts = load_alerts()
            updated = False

            for alert in alerts:
                if not alert.get("active", True):
                    continue
                
                target_p = float(alert.get("target", alert.get("target_price", 0)))
                cond = alert.get("type", alert.get("condition", ">="))
                if cond == "up":
                    cond = ">="
                elif cond == "down":
                    cond = "<="

                c_name = alert.get("contract", alert.get("name", "沪银主力"))
                
                is_hit = False
                direction_txt = ""
                if cond == ">=" and current_price >= target_p:
                    is_hit = True
                    direction_txt = f"涨至 / 突破 (>= {target_p})"
                elif cond == "<=" and current_price <= target_p:
                    is_hit = True
                    direction_txt = f"跌至 / 跌破 (<= {target_p})"

                if is_hit:
                    alert["active"] = False
                    updated = True
                    title = f"【价格预警达成】{c_name}"
                    desp = (
                        f"### 设定的目标价格已触发！\n"
                        f"- 监控标的：{c_name}\n"
                        f"- 预警条件：{direction_txt}\n"
                        f"- 当前最新价：**{current_price}**\n"
                        f"- 触发时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        f"> 提示：此目标价预警已成功触发并通知到手机。"
                    )
                    send_wechat_notification(title, desp)
            
            if updated:
                save_alerts(alerts)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] 暂时未获取到有效的白银价格...")

    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] [错误] 抓取异常: {e}")

def pd_notnull(val):
    return val is not None and str(val) != 'nan'

if __name__ == "__main__":
    is_once_mode = "--once" in sys.argv or os.environ.get("GITHUB_ACTIONS") == "true"
    print("=" * 60)
    print(f" 沪银价格预警 Guard 进程启动 | 模式: {'单次抓取(云端)' if is_once_mode else '死循环盯盘(本地)'}")
    print("=" * 60)
    
    if is_once_mode:
        check_market_data()
        print(f"[{time.strftime('%H:%M:%S')}] 云端单次任务执行完成，正常退出。")
    else:
        while True:
            check_market_data()
            time.sleep(CHECK_INTERVAL)
