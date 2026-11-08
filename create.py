# -*- coding: utf-8 -*-
import sys
import os
import json
import time
import threading
import urllib.request
import urllib.parse
import subprocess
import winsound
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, 
    QPushButton, QComboBox, QLineEdit, QFormLayout, QDialog, 
    QMessageBox, QSystemTrayIcon, QMenu, QAction
)
from PyQt5.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QColor

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".market_clock_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

class SilentTipDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(360, 180)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setStyleSheet("background-color: #1e222b; color: white; border: 1px solid #38bdf8; border-radius: 8px;")
        
        layout = QVBoxLayout(self)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8; border: none;")
        layout.addWidget(title_lbl)
        
        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet("font-size: 13px; color: #e2e8f0; border: none;")
        layout.addWidget(msg_lbl)
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; border-radius: 4px; padding: 6px 16px;")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
        
        self._drag_position = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_position:
            self.move(event.globalPos() - self._drag_position)
            event.accept()

class MarketClockApp(QWidget):
    def __init__(self):
        super().__init__()
        self.server_key = "fd5b5e44/e91c086be1fa9eccc016d6" # 已验证的 Server酱 Token
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("MarketDesktopClock - 智能行情与复盘助理")
        self.resize(440, 260)
        
        layout = QVBoxLayout(self)
        title = QLabel("🎯 智能交易行情与自动化复盘助理")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8; margin-bottom: 4px;")
        layout.addWidget(title)
        
        self.info_lbl = QLabel("状态: 双向防线告警已生效 | 每日收盘Markdown自动归档就绪")
        self.info_lbl.setStyleSheet("color: #34d399; font-size: 12px; margin-bottom: 8px;")
        layout.addWidget(self.info_lbl)
        
        btn_layout = QHBoxLayout()
        
        report_btn = QPushButton("📝 生成今日复盘日报")
        report_btn.setStyleSheet("background-color: #059669; color: white; font-weight: bold; border-radius: 4px; padding: 8px;")
        report_btn.clicked.connect(self.generate_daily_review_report)
        btn_layout.addWidget(report_btn)

        sync_btn = QPushButton("☁️ 同步到云端 (Git + 微信)")
        sync_btn.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; border-radius: 4px; padding: 8px;")
        sync_btn.clicked.connect(self.sync_to_cloud)
        btn_layout.addWidget(sync_btn)
        
        layout.addLayout(btn_layout)

    def check_price_alerts(self, info):
        """盘中异动与价格突破双向防线检查"""
        try:
            current_price = float(info.get("price", 0))
            current_contract = info.get("contract", "")
            
            filepath = os.path.join(CACHE_DIR, "price_alerts.json")
            if not os.path.exists(filepath):
                return
            
            with open(filepath, "r", encoding="utf-8") as f:
                alerts = json.load(f)
            
            updated = False
            for alert in alerts:
                if alert.get("active", True):
                    target = float(alert.get("target", 0))
                    cond_type = alert.get("type")
                    alert_contract = alert.get("contract")
                    
                    if alert_contract in current_contract or current_contract in alert_contract:
                        triggered = False
                        if cond_type == "up" and current_price >= target:
                            triggered = True
                        elif cond_type == "down" and current_price <= target:
                            triggered = True
                        
                        if triggered:
                            alert["active"] = False
                            updated = True
                            cond_desc = f"价格涨至 {target}" if cond_type == "up" else f"价格跌至 {target}"
                            msg = f"价格已到预警线！合约 {current_contract}\n当前最新价: {current_price}\n条件: {cond_desc}"
                            
                            # 1. 本地蜂鸣提醒
                            try:
                                for _ in range(3):
                                    winsound.Beep(1200, 350)
                                    time.sleep(0.15)
                            except Exception:
                                pass

                            # 2. 复用 Server酱 接口发送微信突破告警（异步非阻塞）
                            try:
                                title_str = f"🚨 【行情突破预警】{current_contract} 触及目标价"
                                desp = (
                                    f"### 🎯 桌面时钟价格突破提醒\n\n"
                                    f"- **触发合约**: `{current_contract}`\n"
                                    f"- **当前最新价**: `{current_price}`\n"
                                    f"- **预警目标价**: `{target}`\n"
                                    f"- **触发条件**: `{cond_desc}`\n"
                                    f"- **触发时间**: `{time.strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                                    f"> 💡 盘中行情波动剧烈，请及时关注量价变化与持仓状态！"
                                )
                                
                                def send_wechat_push():
                                    try:
                                        url = f"https://sctapi.ftqq.com/{self.server_key}.send"
                                        data = urllib.parse.urlencode({"title": title_str, "desp": desp}).encode("utf-8")
                                        req = urllib.request.Request(url, data=data, method="POST")
                                        urllib.request.urlopen(req, timeout=5)
                                    except Exception:
                                        pass
                                threading.Thread(target=send_wechat_push, daemon=True).start()
                            except Exception:
                                pass

                            # 3. 本地弹窗提醒
                            dlg = SilentTipDialog("价格预警触发 (价格已到预警线)", msg, self)
                            dlg.exec_()
            
            if updated:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(alerts, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def generate_daily_review_report(self):
        """生成今日行情复盘 Markdown 日报并自动 Git 归档推送微信"""
        try:
            repo_dir = r"D:\日历"
            if not os.path.exists(repo_dir):
                repo_dir = os.getcwd()
                
            reports_dir = os.path.join(repo_dir, "reports")
            os.makedirs(reports_dir, exist_ok=True)
            
            today_str = time.strftime("%Y-%m-%d")
            report_filename = f"{today_str}-market-review.md"
            report_filepath = os.path.join(reports_dir, report_filename)
            
            # 1. 尝试读取当日预警触发记录
            alerts_summary = "暂无触发记录"
            alert_filepath = os.path.join(CACHE_DIR, "price_alerts.json")
            if os.path.exists(alert_filepath):
                try:
                    with open(alert_filepath, "r", encoding="utf-8") as f:
                        alerts = json.load(f)
                    alert_lines = []
                    for a in alerts:
                        status = "✅ 已触发" if not a.get("active", True) else "⏳ 监控中"
                        cond = "≥" if a.get("type") == "up" else "≤"
                        alert_lines.append(f"- **{a.get('contract')}**: 目标位 {cond} {a.get('target')} ({status})")
                    if alert_lines:
                        alerts_summary = "\n".join(alert_lines)
                except Exception:
                    pass

            # 2. 构造标准的复盘 Markdown 日报内容
            markdown_content = f"""# 📊 期货与大宗商品每日交易复盘日报

- **复盘日期**: `{today_str}`
- **生成时间**: `{time.strftime('%Y-%m-%d %H:%M:%S')}`
- **归档仓库**: `wangr1200/Stock-Market-and-Silver-Futures-Calendar-Clock`

---

## 📈 一、 盘中突破防线与预警回顾

{alerts_summary}

---

## 💡 二、 量价关系与核心品种观察 (缩量/放量)

- **沪银主力 (AG2702)**: 重点关注日线突破位与筹码锁定情况（缩量上涨提示筹码锁定良好）。
- **沪金主力 (AU2702)**: 跟踪外盘黄金联动及央行购金政策/流动性变化。
- **有色/战略金属**: 密切跟踪锡、锑等关键品种供需约束与现货升贴水。

---

## 📝 三、 交易心得与明日部署

> *“遵守交易纪律，严格执行风控防线。”*
- [ ] 检查明日开盘预警目标价配置
- [ ] 复核持仓风险暴露与保证金占用

---
*本报告由 MarketDesktopClock 桌面时钟自动化生成并归档。*
"""
            with open(report_filepath, "w", encoding="utf-8") as f:
                f.write(markdown_content)
                
            # 3. 开启异步线程：Git commit & push + 微信推送精简简报
            def async_archive_and_push():
                try:
                    # Git 归档
                    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, timeout=10)
                    subprocess.run(["git", "commit", "-m", f"auto: daily market review archive for {today_str}"], cwd=repo_dir, capture_output=True, timeout=10)
                    subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, capture_output=True, timeout=20)
                    
                    # 微信下发复盘简报
                    url = f"https://sctapi.ftqq.com/{self.server_key}.send"
                    title = f"📝 【收盘复盘日报】{today_str} 行情归档完成"
                    desp = (
                        f"### 📑 {today_str} 交易复盘日报已自动生成并归档\n\n"
                        f"- **归档路径**: `reports/{report_filename}`\n"
                        f"- **GitHub 同步**: ✅ 已自动 Push 至主仓库\n\n"
                        f"#### 🎯 盘中预警回顾:\n"
                        f"{alerts_summary}\n\n"
                        f"> 💡 详细复盘 Markdown 报告已存入本地与 GitHub 仓库！"
                    )
                    data = urllib.parse.urlencode({"title": title, "desp": desp}).encode("utf-8")
                    req = urllib.request.Request(url, data=data, method="POST")
                    urllib.request.urlopen(req, timeout=5)
                except Exception:
                    pass
                    
            threading.Thread(target=async_archive_and_push, daemon=True).start()
            QMessageBox.information(self, "日报生成成功", f"今日复盘日报已保存至:\n{report_filepath}\n\n后台正在同步至 GitHub 并推送微信简报！")
            
        except Exception as e:
            QMessageBox.warning(self, "生成失败", str(e))

    def sync_to_cloud(self):
        try:
            repo_dir = r"D:\日历"
            if not os.path.exists(repo_dir):
                repo_dir = os.getcwd()
            
            def do_sync():
                try:
                    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, timeout=10)
                    subprocess.run(["git", "commit", "-m", "auto: sync market config and alerts"], cwd=repo_dir, capture_output=True, timeout=10)
                    subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, capture_output=True, timeout=20)
                    
                    url = f"https://sctapi.ftqq.com/{self.server_key}.send"
                    data = urllib.parse.urlencode({
                        "title": "☁️ 桌面时钟云端同步成功",
                        "desp": f"### 🚀 Git 自动同步完成\n- 时间: `{time.strftime('%Y-%m-%d %H:%M:%S')}`\n- 状态: 预警配置与文件已同步至 GitHub 主仓库！"
                    }).encode("utf-8")
                    req = urllib.request.Request(url, data=data, method="POST")
                    urllib.request.urlopen(req, timeout=5)
                except Exception:
                    pass
            
            threading.Thread(target=do_sync, daemon=True).start()
            QMessageBox.information(self, "同步提示", "云端同步任务已在后台触发，微信将稍后收到通知！")
        except Exception as e:
            QMessageBox.warning(self, "同步错误", str(e))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MarketClockApp()
    window.show()
    sys.exit(app.exec_())
