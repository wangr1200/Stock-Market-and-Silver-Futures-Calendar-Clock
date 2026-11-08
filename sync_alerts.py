import os
import sys
import shutil
import subprocess
import json
import requests
import datetime

def sync_to_cloud():
    """统一的本地预警配置同步到 Git 云端与微信推送函数"""
    CACHE_DIR = os.path.join(os.path.expanduser("~"), ".market_clock_cache")
    filepath = os.path.join(CACHE_DIR, "price_alerts.json")
    
    if not os.path.exists(filepath):
        return False, "本地未找到 price_alerts.json 文件"

    try:
        # 1. 查找 Git 仓库根目录
        repo_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        if not os.path.exists(os.path.join(repo_dir, ".git")):
            repo_dir = os.getcwd()
        if not os.path.exists(os.path.join(repo_dir, ".git")):
            p = repo_dir
            for _ in range(5):
                if os.path.exists(os.path.join(p, ".git")):
                    repo_dir = p
                    break
                parent = os.path.dirname(p)
                if parent == p:
                    break
                p = parent
        
        # 2. 复制到 Git 目录并执行 Git 提交推送
        git_dir = os.path.join(repo_dir, ".git")
        if os.path.exists(git_dir):
            repo_json_path = os.path.join(repo_dir, "price_alerts.json")
            try:
                shutil.copy(filepath, repo_json_path)
                res_add = subprocess.run(["git", "add", "price_alerts.json"], cwd=repo_dir, capture_output=True, text=True)
                if res_add.returncode == 0:
                    subprocess.run(["git", "commit", "-m", "auto sync price_alerts.json from local GUI"], cwd=repo_dir, capture_output=True, text=True)
                    subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, capture_output=True, text=True)
            except Exception as g_err:
                pass

        # 3. 读取内容并发微信通知
        with open(filepath, "r", encoding="utf-8") as f:
            alerts = json.load(f)

        alerts_summary = ""
        for idx, a in enumerate(alerts):
            c_name = a.get("contract", "")
            c_type = "涨到 (≥)" if a.get("type") == "up" else "跌到 (≤)"
            c_target = a.get("target", 0.0)
            status = "监控中" if a.get("active", True) else "已触发"
            alerts_summary += f"- {idx+1}. **{c_name}** | {c_type} **{c_target}** | {status}\n"

        if not alerts_summary:
            alerts_summary = "暂无活跃预警"

        server_key = "SCT464863Tfmh0nHqPb8JmYygfidSRGa2P"
        url = f"https://sctapi.ftqq.com/{server_key}.send" if server_key else ""
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = "☁️【桌面时钟】预警配置已同步更新"
        desp = (
            f"### 📥 本地新预警已成功同步！\n"
            f"- **同步时间**：{now_str}\n"
            f"- **当前预警总数**：{len(alerts)} 条\n\n"
            f"**当前所有预警列表**：\n{alerts_summary}\n"
            f"> 💡 云端监控进程将在下一轮（60秒内）自动应用最新规则。"
        )
        if server_key:
            requests.post(url, data={"title": title, "desp": desp}, timeout=5)
            
        return True, f"成功同步 {len(alerts)} 条预警到云端并通过微信完成推送"
    except Exception as e:
        return False, str(e)
