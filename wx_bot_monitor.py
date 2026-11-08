import time
import requests
import akshare as ak

# ================= 1. 配置区域 =================
SERVER_CHAN_KEY = "SCT464863Tfmh0nHqPb8JmYygfidSRGa2P"
CHECK_INTERVAL = 60  # 每 60 秒检查一次盘面

# ----------------- 2. 目标价格预警规则表 -----------------
# 你可以在这里自由增减你想监控的目标价（完全对应你在界面设置的预警）
TARGET_ALERTS = [
    {
        "symbol": "AG0",               # 监控合约代码（AG0 为沪银主力）
        "name": "沪银 (AG2702/主力)",
        "condition": ">=",             # '>=' 表示价格涨到或超过，'<=' 表示跌到或低于
        "target_price": 12523.0,       # 你设置的目标价格
        "triggered": False             # 触发状态标识（触发后自动锁定，防止重复轰炸微信）
    },
    # 如果后续想加第二个、第三个目标价，可以直接按下面格式往后加：
    # {
    #     "symbol": "AG0",
    #     "name": "沪银止损位",
    #     "condition": "<=",
    #     "target_price": 11800.0,
    #     "triggered": False
    # }
]
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
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [错误] Server酱返回: {res_json.get('message')}")
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [异常] 发送微信消息失败: {e}")

def check_market_data():
    """检查行情并精准比对目标价格预警"""
    try:
        # 获取实时行情
        try:
            df = ak.futures_zh_realtime(symbol="AG0")
        except Exception:
            df = ak.futures_symbol_mark()

        if df is None or df.empty:
            return

        row = df.iloc[0]
        contract_symbol = str(row.get('symbol', 'AG0'))
        current_price = float(row.get('trade', row.get('price', 0)))
        
        print(f"[{time.strftime('%H:%M:%S')}] 盯盘中 -> 合约: {contract_symbol} | 当前最新价: {current_price}")

        # 遍历所有目标价预警规则
        for alert in TARGET_ALERTS:
            if alert["triggered"]:
                continue  # 触发过后不再重复推送
            
            target_p = alert["target_price"]
            cond = alert["condition"]
            name = alert["name"]
            
            is_hit = False
            direction_txt = ""
            if cond == ">=" and current_price >= target_p:
                is_hit = True
                direction_txt = f"涨至 / 突破 (≥ {target_p})"
            elif cond == "<=" and current_price <= target_p:
                is_hit = True
                direction_txt = f"跌至 / 跌破 (≤ {target_p})"

            if is_hit:
                alert["triggered"] = True  # 锁定状态
                title = f"🎯【价格预警达成】{name}"
                desp = (
                    f"### 🚨 设定的目标价格已触发！\n"
                    f"- **监控标的**：{name}\n"
                    f"- **预警条件**：{direction_txt}\n"
                    f"- **当前最新价**：**{current_price}**\n"
                    f"- **触发时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"> 提示：此目标价预警已成功触发并通知到手机。"
                )
                send_wechat_notification(title, desp)

    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [错误] 抓取异常: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print(" 🎯 纯粹目标价格预警 Guard 进程已启动（已剔除涨跌幅波动提醒）")
    print(f" ⏱️ 轮询频率: 每 {CHECK_INTERVAL} 秒")
    print(" 📌 当前监控的目标价列表:")
    for a in TARGET_ALERTS:
        print(f"    • [{a['name']}] 条件: 价格 {a['condition']} {a['target_price']}")
    print("=" * 60)
    
    while True:
        check_market_data()
        time.sleep(CHECK_INTERVAL)