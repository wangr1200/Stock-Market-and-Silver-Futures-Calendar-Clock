import time
import json
import os
import subprocess
import requests
import akshare as ak

# ================= 1. 配置区域 =================
SERVER_CHAN_KEY = "SCT464863Tfmh0nHqPb8JmYygfidSRGa2P"
CHECK_INTERVAL = 60  # 每 60 秒检查一次盘面
ALERTS_FILE = "price_alerts.json"  # 预警配置文件
# ============================================

def send_wechat_notification(title, desp):
    """通过 Server酱 发送微信推送消息到手机"""
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
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [异常] 发送微信消息失败: {e}")

def load_dynamic_alerts():
    """每次检查前自动执行 git pull 并加载最新的预警配置"""
    try:
        # 1. 自动从 GitHub 拉取最新配置文件，确保云端拿到本地最新同步的内容
        subprocess.run(["git", "pull", "--quiet"], check=False)
    except Exception:
        pass

    alerts = []
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                # 转换格式适配云端监控逻辑
                for item in raw_data:
                    if item.get("active", True):  # 只监控激活状态的
                        alerts.append({
                            "name": f"沪银主力 ({item.get('contract', 'AG0')})",
                            "condition": ">=" if item.get('type') == "up" else "<=",
                            "target_price": float(item.get('target', 0.0)),
                            "triggered": False
                        })
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] [警告] 读取预警配置出错: {e}")
    return alerts

def check_market_data():
    """检查行情并比对动态加载的预警规则"""
    try:
        # 每次轮询前自动同步并加载最新预警
        current_alerts = load_dynamic_alerts()

        # 使用新浪期货主力合约接口获取行情
        df = ak.futures_main_sina()
        if df is None or df.empty:
            print(f"[{time.strftime('%H:%M:%S')}] 未能获取到新浪主力行情数据...")
            return

        current_price = 0.0
        contract_desc = "沪银主力 (AG0)"

        for _, row in df.iterrows():
            symbol = str(row.get('symbol', '')).upper()
            name = str(row.get('name', ''))
            
            if 'AG' in symbol or '银' in name:
                for col in ['trade', 'price', '最新价', '现价']:
                    if col in row:
                        val = row[col]
                        if val is not None and str(val) != 'nan':
                            try:
                                f_val = float(val)
                                if f_val > 0:
                                    current_price = f_val
                                    contract_desc = f"{name} ({symbol})"
                                    break
                            except:
                                pass
                if current_price > 0:
                    break

        if current_price > 0:
            print(f"[{time.strftime('%H:%M:%S')}] 盯盘中 -> 合约: {contract_desc} | 当前最新价: {current_price} | 当前激活预警数: {len(current_alerts)}")

            for alert in current_alerts:
                target_p = alert["target_price"]
                cond = alert["condition"]
                
                is_hit = False
                direction_txt = ""
                if cond == ">=" and current_price >= target_p:
                    is_hit = True
                    direction_txt = f"涨至 / 突破 (≥ {target_p})"
                elif cond == "<=" and current_price <= target_p:
                    is_hit = True
                    direction_txt = f"跌至 / 跌破 (≤ {target_p})"

                if is_hit:
                    title = f"🎯【价格预警达成】{alert['name']}"
                    desp = (
                        f"### 🚨 设定的目标价格已触发！\n"
                        f"- **监控标的**：{contract_desc}\n"
                        f"- **预警条件**：{direction_txt}\n"
                        f"- **当前最新价**：**{current_price}**\n"
                        f"- **触发时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        f"> 提示：此目标价预警已成功触发并通知到手机。"
                    )
                    send_wechat_notification(title, desp)
                    # 触发后可在本地修改状态，云端会自动同步
        else:
            print(f"[{time.strftime('%H:%M:%S')}] 正在等待有效的白银主力价格...")

    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] [错误] 抓取异常: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print(" 🎯 沪银目标价格预警 Guard 进程已启动（全自动JSON动态同步版）")
    print(f" ⏱️ 轮询频率: 每 {CHECK_INTERVAL} 秒（每次轮询自动同步 Git 配置）")
    print("=" * 60)
    
    while True:
        check_market_data()
        time.sleep(CHECK_INTERVAL)