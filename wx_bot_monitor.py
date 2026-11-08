import time
import requests
import akshare as ak

# ================= 1. 配置区域 =================
SERVER_CHAN_KEY = "SCT464863Tfmh0nHqPb8JmYygfidSRGa2P"
CHECK_INTERVAL = 60  # 每 60 秒检查一次盘面

# ----------------- 2. 目标价格预警规则表 -----------------
TARGET_ALERTS = [
    {
        "name": "沪银主力 (AG0)",
        "condition": ">=",             # '>=' 表示价格涨到或超过，'<=' 表示跌到或低于
        "target_price": 12523.0,       # 你设置的目标价格
        "triggered": False             # 触发状态标识
    },
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
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [异常] 发送微信消息失败: {e}")

def check_market_data():
    """检查行情并精准获取沪银实时价格"""
    try:
        # 直接获取白银品种实时行情
        df = ak.futures_zh_spot(symbol="AG0", market="SHFE")
        if df is None or df.empty:
            # 备用方案：获取上期所实时数据并在其中查找 AG
            df = ak.futures_zh_realtime(market="SHFE")

        if df is None or df.empty:
            print(f"[{time.strftime('%H:%M:%S')}] 未能获取到行情数据...")
            return

        current_price = 0.0
        contract_desc = "沪银主力 (AG0)"

        # 遍历查找白银
        for _, row in df.iterrows():
            row_str = str(row.values).upper()
            if 'AG' in row_str or '沪银' in row_str:
                # 尝试提取价格字段（兼容不同接口的列名）
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

        # 如果上面没抓到，尝试用新浪主力表格直接按行匹配
        if current_price == 0:
            df_main = ak.futures_main_sina()
            if df_main is not None and not df_main.empty:
                for _, row in df_main.iterrows():
                    symbol = str(row.get('symbol', '')).upper()
                    name = str(row.get('name', ''))
                    if 'AG' in symbol or '银' in name:
                        current_price = float(row.get('trade', row.get('price', 0)))
                        contract_desc = f"{name} ({symbol})"
                        break

        if current_price > 0:
            print(f"[{time.strftime('%H:%M:%S')}] 盯盘中 -> 合约: {contract_desc} | 当前最新价: {current_price}")

            for alert in TARGET_ALERTS:
                if alert["triggered"]:
                    continue
                
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
                    alert["triggered"] = True
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
        else:
            print(f"[{time.strftime('%H:%M:%S')}] 暂时未获取到有效的白银价格，等待下一轮...")

    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] [错误] 抓取异常: {e}")

def pd_notnull(val):
    return val is not None and str(val) != 'nan'

if __name__ == "__main__":
    print("=" * 60)
    print(" 🎯 沪银目标价格预警 Guard 进程已启动（终极兼容版）")
    print(f" ⏱️ 轮询频率: 每 {CHECK_INTERVAL} 秒")
    print("=" * 60)
    
    while True:
        check_market_data()
        time.sleep(CHECK_INTERVAL)