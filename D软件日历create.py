# -*- coding: utf-8 -*-
import sys
import winsound
import os
import datetime
import requests
import traceback
import random
import json
import winreg
import subprocess
import shutil
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QGraphicsDropShadowEffect, QPushButton, 
                             QDialog, QCalendarWidget, QSlider, QCheckBox, 
                             QFormLayout, QComboBox, QColorDialog, QSystemTrayIcon, QMenu, QAction,
                             QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox, QSpinBox)
from PyQt5.QtCore import Qt, QTimer, QPoint, QDate, QRect, QRectF, pyqtSignal, QObject, QSettings, QThread, pyqtSlot
from PyQt5.QtGui import QColor, QBrush, QDesktopServices, QPainter, QIcon, QPixmap, QPen, QPolygon
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QCloseEvent

CONFIG_DIR = r"D:\软件\日历"
if not os.path.exists(CONFIG_DIR):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
    except Exception:
        CONFIG_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
        if not os.path.exists(CONFIG_DIR) or not os.access(CONFIG_DIR, os.W_OK):
            CONFIG_DIR = os.getcwd()

LOG_FILE = os.path.join(CONFIG_DIR, "error.log")

def safe_float(val, default=0.0):
    try:
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).replace(',', '').strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default

DEFAULT_AG_CONTRACT = "AG0"
DEFAULT_AU_CONTRACT = "AU0"
DEFAULT_AG_PRICE = 12666.0
DEFAULT_AU_PRICE = 885.48
DEFAULT_AG_MULTIPLIER = 15.0
DEFAULT_AU_MULTIPLIER = 1000.0

def log_error(err, context_msg=""):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 5 * 1024 * 1024:
            bak_file = os.path.join(CONFIG_DIR, "error.log.bak")
            if os.path.exists(bak_file):
                os.remove(bak_file)
            os.rename(LOG_FILE, bak_file)

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("[%s] ERROR in %s:\n" % (now_str, context_msg))
            f.write("Type: %s | Message: %s\n" % (type(err).__name__, str(err)))
            f.write("Traceback:\n" + traceback.format_exc() + "\n")
            f.write("-" * 60 + "\n")
    except Exception:
        pass

def cleanup_cache():
    try:
        if not os.path.exists(CONFIG_DIR):
            return
            
        now_ts = datetime.datetime.now().timestamp()
        expire_seconds = 30 * 24 * 3600
        
        for filename in os.listdir(CONFIG_DIR):
            filepath = os.path.join(CONFIG_DIR, filename)
            if os.path.isfile(filepath) and not filename.endswith("error.log"):
                file_mtime = os.path.getmtime(filepath)
                if now_ts - file_mtime > expire_seconds:
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
    except Exception as e:
        log_error(e, "CleanupCache")

HOLIDAY_SCHEDULE = {
    "2026-01-01": {"types": ["A", "HK", "AG"], "reason": "元旦休市"},
    "2026-01-02": {"types": ["A", "HK", "AG"], "reason": "元旦假期休市"},
    "2026-02-16": {"types": ["A", "HK", "AG"], "reason": "春节假期休市"},
    "2026-02-17": {"types": ["A", "HK", "AG"], "reason": "春节假期休市"},
    "2026-02-18": {"types": ["A", "HK", "AG"], "reason": "春节假期休市"},
    "2026-02-19": {"types": ["A", "HK", "AG"], "reason": "春节假期休市"},
    "2026-02-20": {"types": ["A", "AG"], "reason": "春节假期休市"},
    "2026-02-23": {"types": ["A", "AG"], "reason": "春节假期休市"},
    "2026-04-06": {"types": ["A", "HK", "AG"], "reason": "清明节休市"},
    "2026-05-01": {"types": ["A", "HK", "AG"], "reason": "劳动节休市"},
    "2026-05-04": {"types": ["A", "AG"], "reason": "劳动节假期休市"},
    "2026-05-05": {"types": ["A", "AG"], "reason": "劳动节假期休市"},
    "2026-05-25": {"types": ["HK"], "reason": "佛诞日休市（港股）"},
    "2026-06-19": {"types": ["A", "HK", "AG"], "reason": "端午节休市"},
    "2026-07-01": {"types": ["HK"], "reason": "香港特别行政区成立纪念日休市（港股）"},
    "2026-09-25": {"types": ["A", "AG"], "reason": "中秋节休市"},
    "2026-09-28": {"types": ["HK"], "reason": "中秋节翌日休市（港股）"},
    "2026-10-01": {"types": ["A", "HK", "AG"], "reason": "国庆节休市"},
    "2026-10-02": {"types": ["A", "HK", "AG"], "reason": "国庆节假期休市"},
    "2026-10-05": {"types": ["A", "AG"], "reason": "国庆节假期休市"},
    "2026-10-06": {"types": ["A", "AG"], "reason": "国庆节假期休市"},
    "2026-10-07": {"types": ["A", "AG"], "reason": "国庆节假期休市"},
    "2026-10-19": {"types": ["HK"], "reason": "重阳节休市（港股）"},
    "2026-12-25": {"types": ["HK"], "reason": "圣诞节休市（港股）"},

    "2027-01-01": {"types": ["A", "HK", "AG"], "reason": "元旦休市"},
    "2027-02-05": {
        "types": ["A", "HK", "AG"], 
        "reason": "A股/白银休市；港股农历新年前夕半日市（12:00收市）",
        "market_hours": {
            "HK": [{"open": "09:30", "close": "12:00"}]
        }
    },
    "2027-02-08": {"types": ["A", "HK", "AG"], "reason": "春节假期休市（农历年初三）"},
    "2027-02-09": {"types": ["A", "HK", "AG"], "reason": "春节假期休市（农历年初四）"},
    "2027-02-10": {"types": ["A", "AG"], "reason": "春节假期休市"},
    "2027-02-11": {"types": ["A", "AG"], "reason": "春节假期休市"},
    "2027-02-12": {"types": ["A", "AG"], "reason": "春节假期休市"},
    "2027-03-26": {"types": ["HK"], "reason": "耶稣受难节休市（港股）"},
    "2027-03-29": {"types": ["HK"], "reason": "复活节周一休市（港股）"},
    "2027-04-05": {"types": ["A", "HK", "AG"], "reason": "清明节休市"},
    "2027-05-03": {"types": ["A", "AG"], "reason": "劳动节假期休市"},
    "2027-05-04": {"types": ["A", "AG"], "reason": "劳动节假期休市"},
    "2027-05-05": {"types": ["A", "AG"], "reason": "劳动节假期休市"},
    "2027-05-13": {"types": ["HK"], "reason": "佛诞休市（港股）"},
    "2027-06-09": {"types": ["A", "HK", "AG"], "reason": "端午节休市"},
    "2027-07-01": {"types": ["HK"], "reason": "香港特别行政区成立纪念日休市（港股）"},
    "2027-09-15": {"types": ["A", "AG"], "reason": "中秋节休市（A股/白银）"},
    "2027-09-16": {"types": ["HK"], "reason": "中秋节翌日休市（港股）"},
    "2027-10-01": {"types": ["A", "HK", "AG"], "reason": "国庆日休市"},
    "2027-10-04": {"types": ["A", "AG"], "reason": "国庆节假期休市"},
    "2027-10-05": {"types": ["A", "AG"], "reason": "国庆节假期休市"},
    "2027-10-06": {"types": ["A", "AG"], "reason": "国庆节假期休市"},
    "2027-10-07": {"types": ["A", "AG"], "reason": "国庆节假期休市"},
    "2027-10-08": {"types": ["HK"], "reason": "重阳节休市（港股）"},
    "2027-12-24": {
        "types": ["HK"], 
        "reason": "圣诞前夕半日市（12:00收市，港股）",
        "market_hours": {
            "HK": [{"open": "09:30", "close": "12:00"}]
        }
    },
    "2027-12-27": {"types": ["HK"], "reason": "圣诞后首个工作日休市（港股）"},
    "2027-12-31": {
        "types": ["HK"], 
        "reason": "新年前夕半日市（12:00收市，港股）",
        "market_hours": {
            "HK": [{"open": "09:30", "close": "12:00"}]
        }
    }
}

def get_dynamic_macro_events():
    now = datetime.datetime.now()
    y, m = now.year, now.month
    events = [
        {"name": "美国非农就业报告 (NFP)", "time": datetime.datetime(y, m if m <= 11 else 1, (5 if m <= 11 else 5), 20, 30) if datetime.datetime(y, m if m <= 11 else 1, 5, 20, 30) > now else datetime.datetime(y + (1 if m == 12 else 0), (m % 12) + 1, 5, 20, 30)},
        {"name": "美联储利率决议 (FOMC)", "time": datetime.datetime(y, m, 18, 14, 0) if datetime.datetime(y, m, 18, 14, 0) > now else datetime.datetime(y + (1 if m == 12 else 0), (m % 12) + 1, 18, 14, 0)},
        {"name": "美国CPI数据公布", "time": datetime.datetime(y, m, 12, 20, 30) if datetime.datetime(y, m, 12, 20, 30) > now else datetime.datetime(y + (1 if m == 12 else 0), (m % 12) + 1, 12, 20, 30)},
        {"name": "欧洲央行利率决议", "time": datetime.datetime(y, m, 15, 14, 15) if datetime.datetime(y, m, 15, 14, 15) > now else datetime.datetime(y + (1 if m == 12 else 0), (m % 12) + 1, 15, 14, 15)}
    ]
    return events

COLOR_THEMES = {
    "默认暗色": {
        "bg_color": "#1e222b",
        "time_color": "#38bdf8",
        "card_bg": "#262b36",
        "accent": "#0284c7"
    },
    "极简深灰": {
        "bg_color": "#121212",
        "time_color": "#e0e0e0",
        "card_bg": "#1e1e1e",
        "accent": "#333333"
    },
    "科技极光": {
        "bg_color": "#0f172a",
        "time_color": "#34d399",
        "card_bg": "#1e293b",
        "accent": "#059669"
    }
}

def check_autostart():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, "MarketDesktopClock")
        winreg.CloseKey(key)
        return True
    except Exception:
        return False

def set_autostart(enable):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        if enable:
            exe_path = sys.executable
            script_path = os.path.abspath(sys.argv[0])
            if script_path.endswith(".py"):
                cmd = f'"{exe_path}" "{script_path}"'
            else:
                cmd = f'"{script_path}"'
            winreg.SetValueEx(key, "MarketDesktopClock", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, "MarketDesktopClock")
            except Exception:
                pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False

class SilentTipDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(320, 160)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.init_ui(title, message)

    def init_ui(self, title_text, msg_text):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        container = QWidget(self)
        container.setStyleSheet("""
            QWidget {
                background-color: #1e222b;
                border-radius: 12px;
                border: 1px solid rgba(56, 189, 248, 0.3);
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 4)
        container.setGraphicsEffect(shadow)
        main_layout.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title_lbl = QLabel("[提示] " + title_text)
        title_lbl.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: bold; border: none; background: transparent;")
        layout.addWidget(title_lbl)

        msg_lbl = QLabel(msg_text)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet("color: #e2e8f0; font-size: 13px; border: none; background: transparent; line-height: 1.4;")
        layout.addWidget(msg_lbl)

        ok_btn = QPushButton("确定")
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)


class AddPriceAlertDialog(QDialog):
    def __init__(self, current_contract="AG0", current_price=12666.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加价格预警")
        self.resize(340, 240)
        self.setStyleSheet("background-color: #1e222b; color: white;")
        self.parent_window = parent
        self.default_contract = current_contract
        self.current_price = current_price
        self.result_data = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("设置合约价格预警")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff; margin-bottom: 6px;")
        layout.addWidget(title)

        form = QFormLayout()

        self.contract_combo = QComboBox()
        ag_c = getattr(self.parent_window, 'ag_contract', 'AG0') if self.parent_window else "AG0"
        au_c = getattr(self.parent_window, 'au_contract', 'AU0') if self.parent_window else "AU0"
        self.contract_combo.addItems(["沪银 (%s)" % ag_c, "沪金 (%s)" % au_c])
        if "AU" in self.default_contract.upper() or "沪金" in self.default_contract:
            self.contract_combo.setCurrentIndex(1)
        else:
            self.contract_combo.setCurrentIndex(0)
            
        self.contract_combo.setStyleSheet("""
            QComboBox {
                background-color: #262b36; color: #ffffff; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;
            }
            QComboBox QAbstractItemView { background-color: #1e222b; color: white; selection-background-color: #0284c7; }
        """)
        self.contract_combo.currentIndexChanged.connect(self.on_contract_changed)
        form.addRow("选择合约:", self.contract_combo)

        self.cond_combo = QComboBox()
        self.cond_combo.addItems(["合约价格涨到 (>=)", "合约价格跌到 (<=)"])
        self.cond_combo.setStyleSheet("""
            QComboBox {
                background-color: #262b36; color: #e2e8f0;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;
            }
            QComboBox QAbstractItemView { background-color: #1e222b; color: white; selection-background-color: #0284c7; }
        """)
        form.addRow("预警条件:", self.cond_combo)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(1.0, 999999.0)
        self.price_spin.setDecimals(1)
        self.price_spin.setValue(self.current_price)
        self.price_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #262b36; color: #ffffff; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;
            }
        """)
        form.addRow("目标价格:", self.price_spin)

        layout.addLayout(form)

        self.hint_lbl = QLabel("当前最新参考价: %.1f" % self.current_price)
        self.hint_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; margin-top: 4px;")
        layout.addWidget(self.hint_lbl)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定添加")
        ok_btn.setStyleSheet("background-color: #0284c7; color: white; border-radius: 5px; padding: 7px 16px; font-weight: bold;")
        ok_btn.clicked.connect(self.on_ok)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("background-color: #334155; color: white; border-radius: 5px; padding: 7px 16px;")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def on_contract_changed(self, idx):
        if idx == 0:
            self.contract = getattr(self.parent_window, 'ag_contract', 'AG0') if self.parent_window else "AG0"
            p = 12666.0
            if self.parent_window and hasattr(self.parent_window, 'silver_data'):
                try:
                    p = safe_float(self.parent_window.silver_data.get("price", 12666.0))
                except Exception:
                    pass
            self.price_spin.setValue(p)
            self.hint_lbl.setText("当前最新参考价: %.1f" % p)
        else:
            self.contract = getattr(self.parent_window, 'au_contract', 'AU0') if self.parent_window else "AU0"
            p = 885.48
            if self.parent_window and hasattr(self.parent_window, 'gold_data'):
                try:
                    p = safe_float(self.parent_window.gold_data.get("price", 885.48))
                except Exception:
                    pass
            self.price_spin.setValue(p)
            self.hint_lbl.setText("当前最新参考价: %.1f" % p)

    def on_ok(self):
        idx = self.contract_combo.currentIndex()
        if idx == 0:
            self.contract = getattr(self.parent_window, 'ag_contract', 'AG0') if self.parent_window else "AG0"
        else:
            self.contract = getattr(self.parent_window, 'au_contract', 'AU0') if self.parent_window else "AU0"
            
        cond_type = "up" if self.cond_combo.currentIndex() == 0 else "down"
        target_val = self.price_spin.value()
        self.result_data = {
            "contract": self.contract,
            "type": cond_type,
            "target": target_val,
            "active": True,
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.accept()


class PriceAlertDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("价格预警管理")
        self.resize(480, 320)
        self.setStyleSheet("background-color: #1e222b; color: white;")
        self.init_ui()
        self.load_alerts()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        top_row = QHBoxLayout()
        title = QLabel("涨跌目标位预警中心")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        top_row.addWidget(title)
        top_row.addStretch()

        add_btn = QPushButton("+ 添加预警")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7; color: white; border-radius: 4px; padding: 5px 12px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        add_btn.clicked.connect(self.open_add_alert)
        top_row.addWidget(add_btn)
        layout.addLayout(top_row)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["合约", "预警条件", "目标价格", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #161922; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px;
                gridline-color: #262b36; font-size: 13px;
            }
            QHeaderView::section {
                background-color: #262b36; color: #ffffff; font-weight: bold; border: none; padding: 4px;
            }
        """)
        layout.addWidget(self.table)

        bot_row = QHBoxLayout()
        del_btn = QPushButton("删除选中")
        del_btn.setStyleSheet("background-color: #ef4444; color: white; border-radius: 4px; padding: 5px 12px; font-weight: bold;")
        del_btn.clicked.connect(self.delete_selected)
        
        close_btn = QPushButton("关闭窗口")
        close_btn.setStyleSheet("background-color: #334155; color: white; border-radius: 4px; padding: 5px 12px;")
        close_btn.clicked.connect(self.accept)

        sync_cloud_btn = QPushButton("同步到云端")
        sync_cloud_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669; color: white; border-radius: 4px; padding: 5px 12px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #10b981; }
        """)
        sync_cloud_btn.clicked.connect(self.sync_alerts_to_cloud)

        bot_row.addWidget(del_btn)
        bot_row.addWidget(sync_cloud_btn)
        bot_row.addStretch()
        bot_row.addWidget(close_btn)
        layout.addLayout(bot_row)

    def get_alerts_filepath(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        return os.path.join(CONFIG_DIR, "price_alerts.json")

    def load_alerts(self):
        filepath = self.get_alerts_filepath()
        alerts = []
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    alerts = json.load(f)
            except Exception as e:
                log_error(e, "PriceAlert Load")
        
        self.table.setRowCount(len(alerts))
        for row, alert in enumerate(alerts):
            contract_item = QTableWidgetItem(alert.get("contract", ""))
            cond_str = "涨到 (>=)" if alert.get("type") == "up" else "跌到 (<=)"
            cond_item = QTableWidgetItem(cond_str)
            price_item = QTableWidgetItem("%.1f" % alert.get('target', 0.0))
            status_str = "监控中" if alert.get("active", True) else "已触发"
            status_item = QTableWidgetItem(status_str)
            if alert.get("active", True):
                status_item.setForeground(QColor("#38bdf8"))
            else:
                status_item.setForeground(QColor("#22c55e"))

            self.table.setItem(row, 0, contract_item)
            self.table.setItem(row, 1, cond_item)
            self.table.setItem(row, 2, price_item)
            self.table.setItem(row, 3, status_item)

    def save_alerts_to_file(self, alerts):
        try:
            filepath = self.get_alerts_filepath()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(alerts, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def open_add_alert(self):
        curr_contract = "AG0"
        curr_price = 12666.0
        if self.parent_window and hasattr(self.parent_window, 'silver_data'):
            curr_contract = self.parent_window.silver_data.get("contract", "AG0")
            try:
                curr_price = safe_float(self.parent_window.silver_data.get("price", 12666.0))
            except Exception as e:
                log_error(e, "PriceAlert Add")

        dlg = AddPriceAlertDialog(curr_contract, curr_price, self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_data:
            filepath = self.get_alerts_filepath()
            alerts = []
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        alerts = json.load(f)
                except Exception:
                    pass
            alerts.append(dlg.result_data)
            self.save_alerts_to_file(alerts)
            self.load_alerts()

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        filepath = self.get_alerts_filepath()
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    alerts = json.load(f)
                if 0 <= row < len(alerts):
                    alerts.pop(row)
                    self.save_alerts_to_file(alerts)
                    self.load_alerts()
            except Exception as e:
                log_error(e, "PriceAlert Delete")

    def sync_alerts_to_cloud(self):
        try:
            filepath = self.get_alerts_filepath()
            if not os.path.exists(filepath):
                dlg = SilentTipDialog("同步提示", "本地暂无预警配置文件。", self)
                dlg.exec_()
                return

            with open(filepath, "r", encoding="utf-8") as f:
                alerts = json.load(f)

            repo_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            if not os.path.exists(os.path.join(repo_dir, ".git")):
                repo_dir = os.getcwd()

            git_dir = os.path.join(repo_dir, ".git")
            if os.path.exists(git_dir):
                repo_json_path = os.path.join(repo_dir, "price_alerts.json")
                try:
                    shutil.copy(filepath, repo_json_path)
                    subprocess.run(["git", "add", "price_alerts.json"], cwd=repo_dir, capture_output=True, text=True)
                    subprocess.run(["git", "commit", "-m", "auto sync price_alerts.json from local GUI"], cwd=repo_dir, capture_output=True, text=True)
                    subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, capture_output=True, text=True)
                except Exception as g_err:
                    log_error(g_err, "GitSync")

            alerts_summary = ""
            for idx, a in enumerate(alerts):
                c_name = a.get("contract", "")
                c_type = "涨到 (>=)" if a.get("type") == "up" else "跌到 (<=)"
                c_target = a.get("target", 0.0)
                status = "监控中" if a.get("active", True) else "已触发"
                alerts_summary += "- %d. **%s** | %s **%.1f** | %s\n" % (idx+1, c_name, c_type, c_target, status)

            if not alerts_summary:
                alerts_summary = "暂无活跃预警"

            server_key = os.getenv("SERVER_CHAN_KEY", "").strip()
            if not server_key:
                possible_dirs = [
                    CONFIG_DIR,
                    os.getcwd(),
                    os.path.dirname(os.path.abspath(sys.argv[0])),
                    os.path.expanduser("~\.market_clock_cache")
                ]
                for d in possible_dirs:
                    if not d: continue
                    cf = os.path.join(d, "config.json")
                    if os.path.exists(cf):
                        try:
                            with open(cf, "r", encoding="utf-8") as f:
                                cfg = json.load(f)
                                sk = (cfg.get("server_chan_key") or cfg.get("server_key") or "").strip()
                                if sk:
                                    server_key = sk
                                    break
                        except Exception:
                            pass

            if not server_key:
                dlg = SilentTipDialog("微信推送失败", "未检测到 Server酱 SendKey！\n请在 config.json 中配置有效的 server_chan_key。", self)
                dlg.exec_()
                return

            url = "https://sctapi.ftqq.com/%s.send" % server_key
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            title = "[桌面时钟] 预警配置已同步更新"
            desp = (
                "### 本地新预警已成功同步！\n"
                "- **同步时间**：%s\n"
                "- **当前预警总数**：%d 条\n\n"
                "**当前所有预警列表**：\n%s\n"
                "> 云端监控进程将在下一轮（60秒内）自动应用最新规则。"
            ) % (now_str, len(alerts), alerts_summary)

            response = requests.post(url, data={"title": title, "desp": desp}, timeout=10)
            if response.status_code == 200:
                res_json = response.json()
                if res_json.get("code") == 0:
                    dlg = SilentTipDialog("云端同步与微信提醒成功", "最新的价格预警配置已成功处理，并已通过微信成功发送通知！", self)
                    dlg.exec_()
                else:
                    err_msg = res_json.get("message", "未知错误")
                    dlg = SilentTipDialog("微信推送失败", f"Server酱返回错误：\n{err_msg}", self)
                    dlg.exec_()
            else:
                dlg = SilentTipDialog("微信推送失败", f"网络请求异常，状态码：{response.status_code}", self)
                dlg.exec_()

        except Exception as e:
            log_error(e, "SyncAlertsToCloud")
            dlg = SilentTipDialog("同步失败", "推送或发送微信通知异常：\n%s" % e, self)
            dlg.exec_()


class CustomCalendarWidget(QCalendarWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paintCell(self, painter, rect, date):
        super().paintCell(painter, rect, date)
        date_str = date.toString("yyyy-MM-dd")
        if date_str in HOLIDAY_SCHEDULE:
            info = HOLIDAY_SCHEDULE[date_str]
            types = info.get("types", []) if isinstance(info, dict) else info
            
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)

            color_map = {
                "A": QColor("#ef4444"),
                "HK": QColor("#a855f7"),
                "AG": QColor("#38bdf8")
            }

            dot_size = 6
            total_dots = len(types)
            spacing = 4
            total_width = total_dots * dot_size + (total_dots - 1) * spacing
            start_x = rect.x() + (rect.width() - total_width) / 2
            y = rect.y() + rect.height() - 8

            for i, t in enumerate(types):
                if t in color_map:
                    painter.setBrush(QBrush(color_map[t]))
                    painter.setPen(Qt.NoPen)
                    x = start_x + i * (dot_size + spacing)
                    painter.drawEllipse(QRectF(x, y, dot_size, dot_size))

            painter.restore()


class MarketCalendarDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("2026-2027 股市及贵金属期货休市日历")
        self.resize(520, 440)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        title_label = QLabel("2026–2027 年股市及贵金属期货休市安排看板")
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #1e293b; padding: 5px;")
        layout.addWidget(title_label)

        self.calendar = CustomCalendarWidget(self)
        self.calendar.setGridVisible(True)
        self.calendar.setStyleSheet("""
            QCalendarWidget QAbstractItemView:enabled {
                font-size: 15px; color: #334155;
                selection-background-color: #ffffff; selection-color: white;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #1e222b; }
            QCalendarWidget QToolButton { color: white; font-size: 13px; font-weight: bold; }
        """)
        self.calendar.clicked.connect(self.on_date_clicked)
        layout.addWidget(self.calendar)

        legend_label = QLabel("A股休市  |  港股休市  |  贵金属期货休市")
        legend_label.setStyleSheet("color: #475569; font-size: 13px; font-weight: bold; margin-top: 6px;")
        layout.addWidget(legend_label)

        hint_label = QLabel("点击带圆点的日期可查看具体休市原因")
        hint_label.setStyleSheet("color: #64748b; font-size: 13px; font-weight: bold; padding: 1px 2px; line-height: 0.95;")
        layout.addWidget(hint_label)

    def on_date_clicked(self, qdate):
        date_str = qdate.toString("yyyy-MM-dd")
        if date_str in HOLIDAY_SCHEDULE:
            info = HOLIDAY_SCHEDULE[date_str]
            reason = info.get("reason", "休市安排") if isinstance(info, dict) else "休市安排"
            types = info.get("types", [])
            
            type_desc = []
            if "A" in types: type_desc.append("A股")
            if "HK" in types: type_desc.append("港股")
            if "AG" in types: type_desc.append("贵金属期货")
            
            types_str = "、".join(type_desc)
            msg_text = "休市市场：%s\n具体说明：%s" % (types_str, reason)
            dlg = SilentTipDialog("休市提醒 (" + date_str + ")", msg_text, self)
            dlg.exec_()


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("桌面时钟高级设置")
        self.resize(360, 380)
        self.setStyleSheet("background-color: #1e222b; color: white;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.autostart_chk = QCheckBox("开机自动启动")
        self.autostart_chk.setChecked(check_autostart())
        self.autostart_chk.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: bold;")
        self.autostart_chk.stateChanged.connect(self.toggle_autostart)
        form_layout.addRow(self.autostart_chk)

        self.ontop_chk = QCheckBox("窗口始终置顶")
        self.ontop_chk.setChecked(bool(self.parent_window.windowFlags() & Qt.WindowStaysOnTopHint))
        self.ontop_chk.setStyleSheet("color: #e2e8f0; font-size: 13px;")
        self.ontop_chk.stateChanged.connect(self.toggle_ontop)
        form_layout.addRow(self.ontop_chk)

        sep_lbl2 = QLabel("─── 个性化外观 ───")
        sep_lbl2.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold; margin-top: 4px;")
        form_layout.addRow(sep_lbl2)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(COLOR_THEMES.keys()) + ["自定义数字颜色..."])
        settings_file = os.path.join(CONFIG_DIR, "config.json")
        data = {}
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        saved_theme_idx = data.get("theme_index", 0)
        self.theme_combo.setCurrentIndex(saved_theme_idx)
        self.theme_combo.setStyleSheet("""
            QComboBox {
                background-color: #262b36; color: #e2e8f0; border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;
            }
            QComboBox QAbstractItemView { background-color: #1e222b; color: white; selection-background-color: #0284c7; }
        """)
        self.theme_combo.currentIndexChanged.connect(self.change_theme)
        form_layout.addRow("皮肤/主题配色:", self.theme_combo)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(40, 100)
        curr_opacity = int(self.parent_window.windowOpacity() * 100)
        self.opacity_slider.setValue(curr_opacity if curr_opacity > 0 else 95)
        self.opacity_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: #334155; height: 6px; border-radius: 3px; } 
            QSlider::handle:horizontal { background: #38bdf8; width: 14px; margin: -4px 0; border-radius: 7px; }
        """)
        self.opacity_slider.valueChanged.connect(self.change_opacity)
        form_layout.addRow("窗口透明度:", self.opacity_slider)

        layout.addLayout(form_layout)

        close_btn = QPushButton("保存并关闭")
        close_btn.setStyleSheet("background-color: #0284c7; color: white; border-radius: 5px; padding: 7px; font-weight: bold; margin-top: 8px;")
        close_btn.clicked.connect(self.on_save_and_close)
        layout.addWidget(close_btn)

    def toggle_autostart(self, state):
        enable = (state == Qt.Checked)
        success = set_autostart(enable)
        if success:
            msg = "已成功开启开机自启！" if enable else "已取消开机自启。"
            dlg = SilentTipDialog("开机自启设置", msg, self)
            dlg.exec_()
        else:
            dlg = SilentTipDialog("错误", "修改开机自启失败，请尝试以管理员身份运行程序。", self)
            dlg.exec_()

    def toggle_ontop(self, state):
        if self.parent_window:
            flags = self.parent_window.windowFlags()
            if state == Qt.Checked:
                self.parent_window.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
            else:
                self.parent_window.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
            self.parent_window.show()
            self.parent_window.save_settings()

    def change_theme(self, index):
        if not self.parent_window:
            return
        settings_file = os.path.join(CONFIG_DIR, "config.json")
        data = {}
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        data["theme_index"] = index
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        
        theme_names = list(COLOR_THEMES.keys())
        if index < len(theme_names):
            theme_key = theme_names[index]
            theme = COLOR_THEMES[theme_key]
            self.parent_window.apply_theme(
                bg_color=theme["bg_color"],
                time_color=theme["time_color"],
                card_bg=theme["card_bg"],
                accent=theme["accent"]
            )
        else:
            color = QColorDialog.getColor(QColor(self.parent_window.current_time_color), self, "选择自定义数字颜色")
            if color.isValid():
                self.parent_window.apply_theme(
                    bg_color=self.parent_window.current_bg_color,
                    time_color=color.name(),
                    card_bg=self.parent_window.current_card_bg,
                    accent=self.parent_window.current_accent
                )
        self.parent_window.save_settings()

    def change_opacity(self, val):
        if self.parent_window:
            self.parent_window.setWindowOpacity(val / 100.0)
            self.parent_window.save_settings()

    def on_save_and_close(self):
        if self.parent_window:
            self.parent_window.save_settings()
        self.accept()


class BaseQuoteSource:
    def get_quote(self, target_type: str) -> dict:
        raise NotImplementedError


class DomesticCommodityQuoteSource(BaseQuoteSource):
    def get_quote(self, target_type: str) -> dict:
        import json, time, requests
        is_gold = ('金' in target_type or 'AU' in target_type.upper())
        prefix = 'au' if is_gold else 'ag'
        PREFIX_UP = 'AU' if is_gold else 'AG'
        latest, change, chg_pct_val, volume, open_interest, contract_name = 0.0, 0.0, 0.0, '467827', '254876', (PREFIX_UP + '0')
        
        if is_gold:
            try:
                ts = int(time.time() * 1000)
                url = "https://hq.sinajs.cn/list=nf_%s0,nf_%s0&_=%d" % (PREFIX_UP, prefix, ts)
                headers = {'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}
                r = requests.get(url, headers=headers, timeout=2.5)
                if r.status_code == 200:
                    r.encoding = 'gbk'
                    for line in r.text.split(';'):
                        if '="' in line:
                            vals = line.split('="')[1].strip('"
').split(',')
                            if len(vals) > 12:
                                p = safe_float(vals[8], 0.0)
                                if p <= 0:
                                    p = safe_float(vals[6], 0.0)
                                if p <= 0:
                                    p = safe_float(vals[4], 0.0)
                                if p > 10:
                                    latest = p
                                    prev_settle = 0.0
                                    if len(vals) > 10:
                                        s_val = safe_float(vals[10], 0.0)
                                        if 10 < s_val < 999999 and abs(s_val - latest) < latest * 0.2:
                                            prev_settle = s_val
                                    
                                    if prev_settle <= 0:
                                        for idx in [9, 5, 13, 14, 4, 2, 1]:
                                            if len(vals) > idx:
                                                s_val = safe_float(vals[idx], 0.0)
                                                if 10 < s_val < 999999 and abs(s_val - latest) < latest * 0.2:
                                                    prev_settle = s_val
                                                    break
                                                    
                                    if prev_settle <= 0:
                                        prev_settle = latest
                                        
                                    change = latest - prev_settle
                                    chg_pct_val = (change / prev_settle * 100.0) if prev_settle > 0 else 0.0
                                    contract_name = str(vals[12]) if len(vals) > 12 and vals[12] else (PREFIX_UP + '0')
                                    break
            except Exception:
                pass

        if latest <= 0:
            try:
                for secid in ['113.%s0' % PREFIX_UP, '113.%s0' % prefix, '113.%s9999' % PREFIX_UP, '113.%s9999' % prefix]:
                    url_em = 'https://push2.eastmoney.com/api/qt/stock/get?secid=%s&fields=f43,f44,f45,f46,f47,f48,f60,f169,f170' % secid
                    resp = requests.get(url_em, headers={'Referer': 'https://quote.eastmoney.com', 'User-Agent': 'Mozilla/5.0'}, timeout=2.5)
                    if resp.status_code == 200:
                        jdata = resp.json()
                        edata = jdata.get('data')
                        if edata:
                            p = safe_float(edata.get('f43', 0), 0.0)
                            if p > 10:
                                latest = p / 100.0 if p > 1000 else p
                                settle = safe_float(edata.get('f60', 0), 0.0)
                                if settle > 1000:
                                    settle = settle / 100.0
                                elif settle <= 0:
                                    settle = latest
                                if settle > 0:
                                    change = latest - settle
                                    chg_pct_val = (change / settle) * 100.0
                                else:
                                    raw_f169 = safe_float(edata.get('f169', 0), 0.0)
                                    change = raw_f169 / 100.0 if abs(raw_f169) > 100 else raw_f169
                                    raw_f170 = safe_float(edata.get('f170', 0), 0.0)
                                    chg_pct_val = raw_f170 / 100.0 if abs(raw_f170) > 10 else raw_f170
                                volume = str(edata.get('f47', '467827'))
                                open_interest = str(edata.get('f48', '254876'))
                                contract_name = secid.split('.')[1].upper()
                                if latest > 0:
                                    break
            except Exception:
                pass

        if latest <= 0 and not is_gold:
            try:
                ts = int(time.time() * 1000)
                url = 'https://hq.sinajs.cn/list=nf_%s0,nf_%s0&_=%d' % (PREFIX_UP, prefix, ts)
                headers = {'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}
                r = requests.get(url, headers=headers, timeout=2.5)
                if r.status_code == 200:
                    r.encoding = 'gbk'
                    for line in r.text.split(';'):
                        if '="' in line:
                            vals = line.split('="')[1].strip('"
').split(',')
                            if len(vals) > 12:
                                p = safe_float(vals[8], 0.0)
                                if p <= 0:
                                    p = safe_float(vals[6], 0.0)
                                if p <= 0:
                                    p = safe_float(vals[4], 0.0)
                                if p > 10:
                                    latest = p
                                    prev_settle = 0.0
                                    if len(vals) > 10:
                                        s_val = safe_float(vals[10], 0.0)
                                        if 10 < s_val < 999999 and abs(s_val - latest) < latest * 0.2:
                                            prev_settle = s_val
                                    if prev_settle <= 0:
                                        for idx in [9, 5, 13, 14, 4, 2, 1]:
                                            if len(vals) > idx:
                                                s_val = safe_float(vals[idx], 0.0)
                                                if 10 < s_val < 999999 and abs(s_val - latest) < latest * 0.2:
                                                    prev_settle = s_val
                                                    break
                                    if prev_settle <= 0:
                                        prev_settle = latest
                                    change = latest - prev_settle
                                    chg_pct_val = (change / prev_settle * 100.0) if prev_settle > 0 else 0.0
                                    contract_name = str(vals[12]) if len(vals) > 12 and vals[12] else (PREFIX_UP + '0')
                                    break
            except Exception:
                pass

        if latest > 0:
            change_pct = '%+.2f%%' % chg_pct_val
            return {
                'contract': contract_name,
                'price': ('%.2f' % latest) if is_gold else ('%.1f' % latest),
                'change': ('%+.2f' % change) if is_gold else ('%+.1f' % change),
                'change_pct': change_pct,
                'volume': volume,
                'open_interest': open_interest
            }
        return {}


class USStockQuoteSource(BaseQuoteSource):
    def get_quote(self, target_type: str) -> dict:
        is_iau = ("IAU" in target_type.upper() or "黄金" in target_type)
        symbol = "IAU" if is_iau else "SLV"
        
        try:
            sina_sym = f"gb_{symbol.lower()}"
            url = f"https://hq.sinajs.cn/list={sina_sym}"
            headers = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, proxies={"http": None, "https": None}, timeout=3.0)
            if resp.status_code == 200 and '="' in resp.text:
                parts = resp.text.split('="')
                if len(parts) > 1:
                    vals = [v.strip() for v in parts[1].strip('";
').split(',')]
                    if len(vals) > 26 and safe_float(vals[1], 0) > 0:
                        price_val = safe_float(vals[1], 0)
                        prev_close = safe_float(vals[26], 0.0)
                        if prev_close <= 0 and len(vals) > 35:
                            prev_close = safe_float(vals[35], 0.0)
                        if prev_close <= 0:
                            prev_close = price_val
                            
                        change = price_val - prev_close
                        change_pct_val = (change / prev_close * 100.0) if prev_close > 0 else 0.0
                        
                        return {
                            "contract": symbol,
                            "price": "%.3f" % price_val,
                            "change": "%+.3f" % change,
                            "change_pct": "%+.2f%%" % change_pct_val,
                            "volume": str(vals[10]) if len(vals) > 10 else "25000",
                            "open_interest": "80000"
                        }
        except Exception:
            pass

        return {}


class InternationalQuoteSource(BaseQuoteSource):
    def get_quote(self, target_type: str) -> dict:
        is_gold = ("金" in target_type or "XAU" in target_type.upper())
        sina_sym = "hf_XAU" if is_gold else "hf_XAG"
        try:
            url = f"https://hq.sinajs.cn/list={sina_sym}"
            headers = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, proxies={"http": None, "https": None}, timeout=3.0)
            if resp.status_code == 200 and '="' in resp.text:
                parts = resp.text.split('="')
                if len(parts) > 1:
                    vals = parts[1].strip('";
').split(',')
                    if len(vals) > 1 and safe_float(vals[0], 0) > 0:
                        price_val = safe_float(vals[0], 0)
                        settle_p = safe_float(vals[7], 0) if len(vals) > 7 else 0.0
                        if settle_p <= 0 and len(vals) > 8:
                            settle_p = safe_float(vals[8], 0)
                        if settle_p <= 0:
                            settle_p = price_val
                            
                        change = price_val - settle_p
                        change_pct = (change / settle_p * 100.0) if settle_p > 0 else 0.0
                        
                        return {
                            "contract": "XAUUSD" if is_gold else "AGUSDO",
                            "price": ("%.2f" % price_val) if is_gold else ("%.3f" % price_val),
                            "change": ("%+.2f" % change) if is_gold else ("%+.3f" % change),
                            "change_pct": "%+.2f%%" % change_pct,
                            "volume": "35000",
                            "open_interest": "100000"
                        }
        except Exception:
            pass

        try:
            secid = "106.XAUUSD" if is_gold else "106.XAGUSD"
            url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f46,f57,f58,f169,f170,f60,f44"
            headers = {"Referer": "https://quote.eastmoney.com", "User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, proxies={"http": None, "https": None}, timeout=3.0)
            if resp.status_code == 200:
                data = resp.json().get("data")
                if data:
                    raw_latest = safe_float(data.get('f43', 0))
                    if raw_latest <= 0:
                        raw_latest = safe_float(data.get('f44', 0))
                    if raw_latest > 0:
                        latest = raw_latest / 100.0 if raw_latest > 10000 else raw_latest
                        change = safe_float(data.get('f169', 0))
                        change_pct = safe_float(data.get('f170', 0))
                        
                        return {
                            "contract": "XAUUSD" if is_gold else "AGUSDO",
                            "price": ("%.2f" % latest) if is_gold else ("%.3f" % latest),
                            "change": ("%+.2f" % change) if is_gold else ("%+.3f" % change),
                            "change_pct": "%+.2f%%" % change_pct,
                            "volume": "30000",
                            "open_interest": "90000"
                        }
        except Exception:
            pass

        return {}


class CommodityQuoteWorker(QObject):
    data_fetched = pyqtSignal(dict)
    finished = pyqtSignal()

    def __init__(self, target_type="沪银", data_source="多源实时聚合"):
        super().__init__()
        self.target_type = target_type
        self.data_source = data_source
        self.running = True

    def stop(self):
        self.running = False

    @pyqtSlot()
    def do_work(self):
        import time
        retry_count = 0
        last_valid_info = None
        
        while self.running:
            is_us = ("IAU" in self.target_type.upper() or "SLV" in self.target_type.upper() or "ETF" in self.target_type)
            is_intl = ("伦敦" in self.target_type or "XAU" in self.target_type.upper() or "AGUS" in self.target_type.upper())
            try:
                if is_us:
                    source = USStockQuoteSource()
                elif is_intl:
                    source = InternationalQuoteSource()
                else:
                    source = DomesticCommodityQuoteSource()
                info = source.get_quote(self.target_type)
                if info and safe_float(info.get("price", "0")) > 0:
                    last_valid_info = info
                    self.data_fetched.emit(info)
                    retry_count = 0
                elif last_valid_info is not None:
                    self.data_fetched.emit(last_valid_info)
            except Exception:
                retry_count += 1
                if last_valid_info is not None:
                    self.data_fetched.emit(last_valid_info)

            sleep_sec = 3.0
            if retry_count > 3:
                sleep_sec = min(10.0, 2.0 * (2 ** (retry_count - 3)))
            
            for _ in range(int(sleep_sec * 10)):
                if not self.running:
                    break
                time.sleep(0.1)
        self.finished.emit()


class ProfitLossCalculatorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("实时盈亏计算器")
        self.resize(360, 410)
        self.setStyleSheet("background-color: #1e222b; color: white;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("实时持仓盈亏与佣金计算器")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)

        self.comm_combo = QComboBox()
        self.comm_combo.addItems(["沪银 (AG) - 15千克/手", "沪金 (AU) - 1000克/手"])
        self.comm_combo.setStyleSheet("""
            QComboBox {
                background-color: #262b36; color: #ffffff; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;
            }
            QComboBox QAbstractItemView { background-color: #1e222b; color: white; selection-background-color: #0284c7; }
        """)

        saved_comm_idx = 0
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            saved_comm_idx = self.parent_window.saved_calc_params.get("comm_idx", 0)
        self.comm_combo.setCurrentIndex(saved_comm_idx)

        lbl0 = QLabel("计算品种:")
        lbl0.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: bold;")
        form.addRow(lbl0, self.comm_combo)

        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["做多 (Buy Long)", "做空 (Sell Short)"])
        self.dir_combo.setStyleSheet("""
            QComboBox {
                background-color: #262b36; color: #ffffff; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;
            }
            QComboBox QAbstractItemView { background-color: #1e222b; color: white; selection-background-color: #0284c7; }
        """)
        
        saved_dir_idx = 1
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            saved_dir_idx = self.parent_window.saved_calc_params.get("dir_idx", 1)
        self.dir_combo.setCurrentIndex(saved_dir_idx)

        default_p = 12666.0 if saved_comm_idx == 0 else 885.48
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            saved_p = self.parent_window.saved_calc_params.get("open_price", None)
            if saved_p is not None:
                default_p = saved_p

        self.open_price_spin = QDoubleSpinBox()
        self.open_price_spin.setRange(0.1, 999999.0)
        self.open_price_spin.setDecimals(1)
        self.open_price_spin.setValue(default_p)
        self.open_price_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #262b36; color: #ffffff; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;
            }
        """)

        lbl2 = QLabel("开仓价格:")
        lbl2.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: bold;")
        form.addRow(lbl2, self.open_price_spin)

        saved_lots = 1
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            saved_lots = self.parent_window.saved_calc_params.get("lots", 1)

        self.lots_spin = QSpinBox()
        self.lots_spin.setRange(1, 10000)
        self.lots_spin.setValue(saved_lots)
        self.lots_spin.setStyleSheet("""
            QSpinBox {
                background-color: #262b36; color: #ffffff; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;
            }
        """)

        lbl3 = QLabel("持仓手数:")
        lbl3.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: bold;")
        form.addRow(lbl3, self.lots_spin)

        saved_comm = 0.0090
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            saved_comm = self.parent_window.saved_calc_params.get("comm_rate", 0.0090)

        self.comm_spin = QDoubleSpinBox()
        self.comm_spin.setRange(0.0, 1.0)
        self.comm_spin.setDecimals(4)
        self.comm_spin.setSingleStep(0.001)
        self.comm_spin.setValue(saved_comm)
        self.comm_spin.setSuffix("%")
        self.comm_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #262b36; color: #ffffff; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;
            }
        """)

        lbl4 = QLabel("单边佣金费率:")
        lbl4.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: bold;")
        form.addRow(lbl4, self.comm_spin)

        layout.addLayout(form)

        self.result_card = QWidget()
        self.result_card.setStyleSheet("background-color: #141820; border-radius: 8px; border: 1px solid rgba(56, 189, 248, 0.2);")
        card_layout = QVBoxLayout(self.result_card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(4)

        self.pnl_title_lbl = QLabel("扣除来回佣金后净盈亏")
        self.pnl_title_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; border: none;")
        self.pnl_title_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.pnl_title_lbl)

        self.pnl_val_lbl = QLabel("+0.0 元")
        self.pnl_val_lbl.setStyleSheet("color: #ef4444; font-size: 18px; font-weight: bold; border: none;")
        self.pnl_val_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.pnl_val_lbl)

        self.comm_fee_lbl = QLabel("来回佣金: 0.0 元")
        self.comm_fee_lbl.setStyleSheet("color: #facc15; font-size: 11px; border: none;")
        self.comm_fee_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.comm_fee_lbl)

        self.info_lbl = QLabel("当前现价: --")
        self.info_lbl.setStyleSheet("color: #64748b; font-size: 10px; border: none;")
        self.info_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.info_lbl)

        layout.addWidget(self.result_card)

        save_close_btn = QPushButton("保存并关闭窗口")
        save_close_btn.setStyleSheet("background-color: #0284c7; color: white; border-radius: 5px; padding: 7px; font-weight: bold;")
        save_close_btn.clicked.connect(self.on_save_and_close)
        layout.addWidget(save_close_btn)

        self.comm_combo.currentIndexChanged.connect(self.on_commodity_combo_changed)
        self.dir_combo.currentIndexChanged.connect(self.on_param_changed)
        self.open_price_spin.valueChanged.connect(self.on_param_changed)
        self.lots_spin.valueChanged.connect(self.on_param_changed)
        self.comm_spin.valueChanged.connect(self.on_param_changed)

        self.calculate()

    def on_commodity_combo_changed(self, idx):
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params') and self.parent_window.saved_calc_params.get("comm_idx") == idx:
            return
        if idx == 0:
            self.open_price_spin.setValue(12666.0)
        else:
            self.open_price_spin.setValue(885.48)
        self.calculate()
        self.save_current_params()

    def on_param_changed(self):
        self.calculate()
        self.save_current_params()

    def calculate(self):
        try:
            comm_idx = self.comm_combo.currentIndex()
            comm_type = "沪银" if comm_idx == 0 else "沪金"
            mult = 15.0 if comm_idx == 0 else 1000.0
            mult_unit = "千克/手" if comm_idx == 0 else "克/手"

            curr_p = 12666.0 if comm_type == "沪银" else 885.48
            if self.parent_window:
                try:
                    if comm_type == "沪银" and hasattr(self.parent_window, 'silver_data'):
                        curr_p = safe_float(self.parent_window.silver_data.get('price', 12666.0), 12666.0)
                    elif comm_type == "沪金" and hasattr(self.parent_window, 'gold_data'):
                        curr_p = safe_float(self.parent_window.gold_data.get('price', 885.48), 885.48)
                except Exception:
                    pass

            open_p = self.open_price_spin.value()
            lots = self.lots_spin.value()
            is_long = (self.dir_combo.currentIndex() == 0)

            diff = (curr_p - open_p) if is_long else (open_p - curr_p)
            gross_pnl = diff * mult * lots

            single_rate = self.comm_spin.value() / 100.0
            round_rate = single_rate * 2.0

            open_turnover = open_p * mult * lots
            total_commission = open_turnover * single_rate * 2.0
            net_pnl = gross_pnl - total_commission

            self.info_lbl.setText("当前%s参考价: %.1f  |  乘数: %d%s" % (comm_type, curr_p, int(mult), mult_unit))
            self.comm_fee_lbl.setText("来回佣金扣除: -%.1f 元 (双边费率: %.3f%%)" % (total_commission, round_rate*100))

            if net_pnl >= 0:
                self.pnl_val_lbl.setText(f"净浮盈: +{net_pnl:,.1f} 元")
                self.pnl_val_lbl.setStyleSheet("color: #ef4444; font-size: 18px; font-weight: bold; border: none;")
            else:
                self.pnl_val_lbl.setText(f"净浮亏: {net_pnl:,.1f} 元")
                self.pnl_val_lbl.setStyleSheet("color: #22c55e; font-size: 18px; font-weight: bold; border: none;")
        except Exception as e:
            log_error(e, "CalculatorCalculate")

    def save_current_params(self):
        if self.parent_window:
            self.parent_window.saved_calc_params = {
                "comm_idx": self.comm_combo.currentIndex(),
                "dir_idx": self.dir_combo.currentIndex(),
                "open_price": self.open_price_spin.value(),
                "lots": self.lots_spin.value(),
                "comm_rate": self.comm_spin.value()
            }
            self.parent_window.update_compact_pnl()
            self.parent_window.save_settings()

    def on_save_and_close(self):
        self.save_current_params()
        self.accept()


class ClockWindow(QWidget):
    def load_settings(self):
        settings_file = os.path.join(CONFIG_DIR, "config.json")
        data = {}
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        
        theme_idx = data.get("theme_index", 0)
        theme_names = list(COLOR_THEMES.keys())
        if 0 <= theme_idx < len(theme_names):
            t_key = theme_names[theme_idx]
            t = COLOR_THEMES[t_key]
            self.apply_theme(t["bg_color"], t["time_color"], t["card_bg"], t["accent"])
        
        opacity = data.get("opacity", 0.95)
        self.setWindowOpacity(opacity)
        
        ontop = data.get("ontop", True)
        flags = self.windowFlags()
        if ontop:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        
        self.is_locked = data.get("locked", False)
        if self.is_locked:
            self.lock_btn.setText("[锁]")
        else:
            self.lock_btn.setText("[开]")

        x = data.get("pos_x", -1)
        y = data.get("pos_y", -1)
        if x != -1 and y != -1:
            self.move(x, y)

        calc_comm_idx = data.get("calc_comm_idx", 0)
        calc_dir = data.get("calc_dir_idx", 1)
        calc_price = data.get("calc_open_price", 12335.0)
        calc_lots = data.get("calc_lots", 1)
        calc_comm = data.get("calc_comm_rate", 0.0090)
        
        self.saved_calc_params = {
            "comm_idx": calc_comm_idx,
            "dir_idx": calc_dir,
            "open_price": calc_price,
            "lots": calc_lots,
            "comm_rate": calc_comm
        }
        self.update_compact_pnl()

    def save_settings(self):
        settings_file = os.path.join(CONFIG_DIR, "config.json")
        theme_idx = 0
        if hasattr(self, 'current_bg_color'):
            theme_names = list(COLOR_THEMES.keys())
            for idx, name in enumerate(theme_names):
                if COLOR_THEMES[name]["bg_color"] == self.current_bg_color:
                    theme_idx = idx
                    break

        old_cfg = {}
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as sf:
                    old_cfg = json.load(sf)
            except Exception:
                pass

        data = {
            "theme_index": theme_idx,
            "opacity": self.windowOpacity(),
            "ontop": bool(self.windowFlags() & Qt.WindowStaysOnTopHint),
            "locked": self.is_locked,
            "pos_x": self.x(),
            "pos_y": self.y(),
            "calc_comm_idx": self.saved_calc_params.get("comm_idx", 0),
            "calc_dir_idx": self.saved_calc_params.get("dir_idx", 1),
            "calc_open_price": self.saved_calc_params.get("open_price", 12335.0),
            "calc_lots": self.saved_calc_params.get("lots", 1),
            "calc_comm_rate": self.saved_calc_params.get("comm_rate", 0.0090)
        }

        existing_key = old_cfg.get("server_chan_key", "") or old_cfg.get("server_key", "")
        if existing_key:
            data["server_chan_key"] = existing_key

        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            if os.path.exists(settings_file):
                try:
                    os.chmod(settings_file, 0o666)
                except Exception:
                    pass
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log_error(e, "SaveSettings")

    def __init__(self):
        super().__init__()
        self.drag_position = QPoint()
        self.is_locked = False
        self.is_forced_exit = False
        self.is_docked = False
        self.normal_geometry = QRect()
        
        self.current_bg_color = "#1e222b"
        self.current_time_color = "#38bdf8"
        self.current_card_bg = "#262b36"
        self.current_accent = "#0284c7"

        self.saved_calc_params = {"comm_idx": 0, "dir_idx": 1, "open_price": 12335.0, "lots": 1, "comm_rate": 0.0090}
        self.cached_holiday_text = "距离下一节假日：元旦"
        
        self.ag_contract = "AG0"
        self.au_contract = "AU0"
        
        self.silver_data = {
            "contract": "AG0",
            "price": "12687.0",
            "change": "+77.0",
            "change_pct": "+0.61%",
            "volume": "293843",
            "open_interest": "248773"
        }
        self.gold_data = {
            "contract": "AU0",
            "price": "885.5",
            "change": "+8.50",
            "change_pct": "+0.97%",
            "volume": "189766",
            "open_interest": "140200"
        }
        self.xau_data = {
            "contract": "XAUUSD",
            "price": "4105.58",
            "change": "+36.42",
            "change_pct": "+0.89%",
            "volume": "25000",
            "open_interest": "80000"
        }
        self.xag_data = {
            "contract": "AGUSDO",
            "price": "52.660",
            "change": "+0.770",
            "change_pct": "+1.48%",
            "volume": "25000",
            "open_interest": "80000"
        }
        self.iau_data = {
            "contract": "IAU",
            "price": "76.140",
            "change": "-1.640",
            "change_pct": "-2.11%",
            "volume": "25000",
            "open_interest": "80000"
        }
        self.slv_data = {
            "contract": "SLV",
            "price": "46.835",
            "change": "-1.305",
            "change_pct": "-2.71%",
            "volume": "25000",
            "open_interest": "80000"
        }

        self.init_ui()
        self.load_settings()
        self.init_tray()
        self.init_workers()
        cleanup_cache()

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.95)

        self.container = QWidget(self)
        self.container.setObjectName("MainContainer")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 5)
        self.container.setGraphicsEffect(shadow)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.addWidget(self.container)

        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(16, 8, 16, 12)
        c_layout.setSpacing(0)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        
        self.lock_btn = QPushButton("[锁]")
        self.lock_btn.setFixedSize(32, 28)
        self.lock_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 13px; font-weight: bold; color: #ffffff; } QPushButton:hover { background-color: rgba(255,255,255,0.1); border-radius: 4px; }")
        self.lock_btn.clicked.connect(self.toggle_lock)

        self.dock_btn = QPushButton("◀")
        self.dock_btn.setFixedSize(28, 28)
        self.dock_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 13px; color: #ffffff; font-weight: bold; } QPushButton:hover { background-color: rgba(255,255,255,0.1); border-radius: 4px; }")
        self.dock_btn.clicked.connect(self.toggle_dock)

        self.calc_btn = QPushButton("🧮")
        self.calc_btn.setFixedSize(28, 28)
        self.calc_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 15px; color: #22c55e; } QPushButton:hover { background-color: rgba(255,255,255,0.1); border-radius: 4px; }")
        self.calc_btn.clicked.connect(self.open_calculator)

        self.alert_btn = QPushButton("🔔")
        self.alert_btn.setFixedSize(28, 28)
        self.alert_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 15px; color: #ffffff; } QPushButton:hover { background-color: rgba(255,255,255,0.1); border-radius: 4px; }")
        self.alert_btn.clicked.connect(self.open_price_alert)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 15px; color: #a1a1aa; } QPushButton:hover { color: #ffffff; background-color: rgba(255,255,255,0.1); border-radius: 4px; }")
        self.settings_btn.clicked.connect(self.open_settings)

        top_bar.addWidget(self.lock_btn)
        top_bar.addWidget(self.dock_btn)
        top_bar.addWidget(self.calc_btn)
        top_bar.addWidget(self.alert_btn)
        top_bar.addWidget(self.settings_btn)
        top_bar.addStretch()

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 15px; color: #a1a1aa; } QPushButton:hover { color: #ffffff; background-color: rgba(255,255,255,0.1); border-radius: 4px; }")
        self.close_btn.clicked.connect(self.hide)
        top_bar.addWidget(self.close_btn)
        c_layout.addLayout(top_bar)

        self.time_holiday_card = QWidget()
        self.time_holiday_card.setStyleSheet("QWidget { background-color: transparent; border: none; }")
        th_layout = QVBoxLayout(self.time_holiday_card)
        th_layout.setContentsMargins(4, 0, 4, 0)
        th_layout.setSpacing(0)

        self.time_holiday_board = QLabel()
        self.time_holiday_board.setAlignment(Qt.AlignCenter)
        th_layout.addWidget(self.time_holiday_board)

        c_layout.addWidget(self.time_holiday_card)

        self.status_card = QWidget()
        self.status_card.setStyleSheet("QWidget { background-color: %s; border-radius: 8px; border: 1px solid rgba(255,255,255,0.06); }" % self.current_card_bg)
        self.status_card.setFixedHeight(48)
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(10, 2, 10, 2)
        status_layout.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        self.stock_status_label = QLabel("股市：已收盘")
        self.stock_status_label.setStyleSheet("color: #f1f5f9; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        
        self.cal_btn = QPushButton("休市日历")
        self.cal_btn.setStyleSheet("QPushButton { background-color: #262b36; color: #f87171; border: 1px solid rgba(248, 113, 113, 0.3); border-radius: 4px; padding: 1px 4px; font-size: 11px; font-weight: bold; } QPushButton:hover { background-color: #333b4d; }")
        self.cal_btn.clicked.connect(self.show_calendar)
        
        top_row.addWidget(self.stock_status_label)
        top_row.addStretch()
        top_row.addWidget(self.cal_btn)
        status_layout.addLayout(top_row)

        bot_row = QHBoxLayout()
        bot_row.setContentsMargins(0, 0, 0, 0)
        self.silver_status_label = QLabel("贵金属期货：监控中")
        self.silver_status_label.setStyleSheet("color: #f1f5f9; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        bot_row.addWidget(self.silver_status_label)
        bot_row.addStretch()
        
        status_layout.addLayout(bot_row)

        c_layout.addWidget(self.status_card)

        self.silver_board = QLabel()
        self.silver_board.setAlignment(Qt.AlignCenter)
        self.silver_board.setStyleSheet("QLabel { background-color: %s; border-radius: 6px; padding: 1px 2px; margin-top: -2px; margin-bottom: -2px; border: 1px solid rgba(255,255,255,0.06); }" % self.current_card_bg)
        self.update_silver_board_ui()
        c_layout.addWidget(self.silver_board)

        self.compact_pnl_card = QWidget()
        self.compact_pnl_card.setStyleSheet("QWidget { background-color: #141820; border-radius: 6px; margin-top: 1px; margin-bottom: 1px; border: 1px solid rgba(56, 189, 248, 0.3); }")
        compact_layout = QVBoxLayout(self.compact_pnl_card)
        compact_layout.setContentsMargins(2, 0, 2, 0)
        compact_layout.setSpacing(0)

        self.compact_pnl_board = QLabel()
        self.compact_pnl_board.setAlignment(Qt.AlignCenter)
        self.compact_pnl_board.setStyleSheet("background: transparent; border: none;")
        compact_layout.addWidget(self.compact_pnl_board)

        c_layout.addWidget(self.compact_pnl_card)

        self.macro_board = QLabel()
        self.macro_board.setAlignment(Qt.AlignCenter)
        self.macro_board.setStyleSheet("QLabel { background-color: #141820; border-radius: 6px; padding: 0px 2px; margin: -10px 0px; border: 1px solid rgba(255,255,255,0.06); }"); self.macro_board.setFixedHeight(54)
        c_layout.addWidget(self.macro_board)

        self.apply_theme(self.current_bg_color, self.current_time_color, self.current_card_bg, self.current_accent)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)
        self.update_clock()

        self.resize(340, 620)

    def init_workers(self):
        self.ag_thread = QThread()
        self.ag_worker = CommodityQuoteWorker("沪银", "多源实时聚合")
        self.ag_worker.moveToThread(self.ag_thread)
        self.ag_thread.started.connect(self.ag_worker.do_work)
        self.ag_worker.data_fetched.connect(self.on_silver_data_updated)
        self.ag_thread.start()

        self.au_thread = QThread()
        self.au_worker = CommodityQuoteWorker("沪金", "多源实时聚合")
        self.au_worker.moveToThread(self.au_thread)
        self.au_thread.started.connect(self.au_worker.do_work)
        self.au_worker.data_fetched.connect(self.on_gold_data_updated)
        self.au_thread.start()

        self.xau_thread = QThread()
        self.xau_worker = CommodityQuoteWorker("伦敦金", "国际实时聚合")
        self.xau_worker.moveToThread(self.xau_thread)
        self.xau_thread.started.connect(self.xau_worker.do_work)
        self.xau_worker.data_fetched.connect(self.on_xau_data_updated)
        self.xau_thread.start()

        self.xag_thread = QThread()
        self.xag_worker = CommodityQuoteWorker("伦敦银现", "国际实时聚合")
        self.xag_worker.moveToThread(self.xag_thread)
        self.xag_thread.started.connect(self.xag_worker.do_work)
        self.xag_worker.data_fetched.connect(self.on_xag_data_updated)
        self.xag_thread.start()

        self.iau_thread = QThread()
        self.iau_worker = CommodityQuoteWorker("IAU", "美股实时聚合")
        self.iau_worker.moveToThread(self.iau_thread)
        self.iau_thread.started.connect(self.iau_worker.do_work)
        self.iau_worker.data_fetched.connect(self.on_iau_data_updated)
        self.iau_thread.start()

        self.slv_thread = QThread()
        self.slv_worker = CommodityQuoteWorker("SLV", "美股实时聚合")
        self.slv_worker.moveToThread(self.slv_thread)
        self.slv_thread.started.connect(self.slv_worker.do_work)
        self.slv_worker.data_fetched.connect(self.on_slv_data_updated)
        self.slv_thread.start()

    def update_compact_pnl(self):
        try:
            p_data = getattr(self, 'saved_calc_params', {"comm_idx": 0, "dir_idx": 1, "open_price": 12335.0, "lots": 1, "comm_rate": 0.0090})
            comm_idx = p_data.get("comm_idx", 0)
            comm_type = "沪银" if comm_idx == 0 else "沪金"
            mult = 15.0 if comm_idx == 0 else 1000.0
            mult_unit = "千克/手" if comm_idx == 0 else "克/手"

            curr_p = safe_float(self.silver_data.get('price', 12666.0), 12666.0) if comm_type == "沪银" else safe_float(self.gold_data.get('price', 885.48), 885.48)

            open_p = p_data.get("open_price", 12335.0)
            lots = p_data.get("lots", 1)
            dir_idx = p_data.get("dir_idx", 1)
            is_long = (dir_idx == 0)

            dir_str = "多头" if is_long else "空头"
            open_str = "%s开仓价: %.1f  (%d手)" % (dir_str, open_p, lots)

            alert_str = "预警平仓价: 暂无活跃预警"
            try:
                alert_filepath = os.path.join(CONFIG_DIR, "price_alerts.json")
                if os.path.exists(alert_filepath):
                    with open(alert_filepath, "r", encoding="utf-8") as af:
                        alerts_list = json.load(af)
                        for al in alerts_list:
                            if al.get("active", True):
                                c_name = al.get("contract", "")
                                if (comm_type == "沪银" and ("AG" in c_name.upper() or "银" in c_name)) or                                    (comm_type == "沪金" and ("AU" in c_name.upper() or "金" in c_name)):
                                    t_val = safe_float(al.get("target", 0))
                                    t_type = al.get("type", "up")
                                    if t_type == "up":
                                        alert_str = "预警平仓价: 涨到 " + f"{t_val:.1f}" + "自动平仓"
                                    else:
                                        alert_str = "预警平仓价: 跌到 " + f"{t_val:.1f}" + "自动平仓"
                                    break
            except Exception:
                pass

            curr_price_str = "当前%s实时价: %.1f" % (comm_type, curr_p)

            diff = (curr_p - open_p) if is_long else (open_p - curr_p)
            gross_pnl = diff * mult * lots

            single_rate = p_data.get("comm_rate", 0.0090) / 100.0
            round_rate = single_rate * 2.0

            open_turnover = open_p * mult * lots
            total_commission = open_turnover * single_rate * 2.0
            net_pnl = gross_pnl - total_commission

            comm_str = "来回佣金扣除: -%.1f 元 (双边费率: %.3f%%)" % (total_commission, round_rate*100)

            if net_pnl >= 0:
                pnl_color = "#ef4444"
                pnl_str = f"净浮盈: +{net_pnl:,.1f} 元"
            else:
                pnl_color = "#22c55e"
                pnl_str = f"净浮亏: {net_pnl:,.1f} 元"

            if hasattr(self, 'compact_pnl_board'):
                html = (
                    '<table width="100%%" cellspacing="0" cellpadding="0" style="margin: 0px; padding: 2px 0px; border-collapse: collapse;">'
                    '<tr><td align="center" style="font-size: 19px; font-weight: bold; color: #a855f7; margin: 0px; padding: 3px 0px; border: none;">%s</td></tr>'
                    '<tr><td align="center" style="font-size: 19px; font-weight: bold; color: %s; margin: 0px; padding: 3px 0px; border: none;">%s</td></tr>'
                    '<tr><td align="center" style="font-size: 19px; font-weight: bold; color: #ffffff; margin: 0px; padding: 3px 0px; border: none;">%s</td></tr>'
                    '<tr><td align="center" style="font-size: 19px; font-weight: bold; color: #f472b6; margin: 0px; padding: 3px 0px; border: none;">%s</td></tr>'
                    '<tr><td align="center" style="font-size: 12px; font-weight: bold; color: #facc15; margin: 0px; padding: 3px 0px; border: none;">%s</td></tr>'
                    '</table>'
                ) % (curr_price_str, pnl_color, pnl_str, open_str, alert_str, comm_str)
                self.compact_pnl_board.setStyleSheet("background: transparent; border: none; padding: 0px; margin: 0px;")
                self.compact_pnl_board.setText(html)
        except Exception as e:
            log_error(e, "UpdateCompactPnL")

    def on_silver_data_updated(self, info):
        self.silver_data.update(info)
        contract = info.get("contract", "")
        if contract and len(contract) >= 4:
            self.ag_contract = contract
        self.update_silver_board_ui()
        self.update_compact_pnl()
        self.check_price_alerts(info)

    def on_xau_data_updated(self, info):
        self.xau_data.update(info)
        self.update_silver_board_ui()

    def on_iau_data_updated(self, info):
        self.iau_data.update(info)
        self.update_silver_board_ui()

    def on_slv_data_updated(self, info):
        self.slv_data.update(info)
        self.update_silver_board_ui()

    def on_xag_data_updated(self, info):
        self.xag_data.update(info)
        self.update_silver_board_ui()

    def on_gold_data_updated(self, info):
        self.gold_data.update(info)
        contract = info.get("contract", "")
        if contract and len(contract) >= 4:
            self.au_contract = contract
        self.update_silver_board_ui()
        self.check_price_alerts(info)

    def check_price_alerts(self, info):
        try:
            current_price = safe_float(info.get("price", 0))
            current_contract = info.get("contract", "")
            
            filepath = os.path.join(CONFIG_DIR, "price_alerts.json")
            if not os.path.exists(filepath):
                return
            
            with open(filepath, "r", encoding="utf-8") as f:
                alerts = json.load(f)
            
            updated = False
            for alert in alerts:
                if alert.get("active", True):
                    target = safe_float(alert.get("target", 0))
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
                            try:
                                import time
                                for _ in range(3):
                                    winsound.Beep(1200, 350)
                                    time.sleep(0.15)
                            except Exception:
                                pass
                            
                            try:
                                server_key = ""
                                config_file = os.path.join(CONFIG_DIR, "config.json")
                                if os.path.exists(config_file):
                                    with open(config_file, "r", encoding="utf-8") as cf:
                                        cfg = json.load(cf)
                                        server_key = (cfg.get("server_chan_key") or cfg.get("server_key") or "").strip()
                                if not server_key:
                                    server_key = os.getenv("SERVER_CHAN_KEY", "").strip()
                                
                                if server_key:
                                    url = "https://sctapi.ftqq.com/%s.send" % server_key
                                    title = "【价格预警达成】%s" % alert_contract
                                    direction_txt = "涨至 / 突破 (>= %.1f)" % target if cond_type == "up" else "跌至 / 跌破 (<= %.1f)" % target
                                    desp = (
                                        "### 设定的目标价格已触发！\n"
                                        "- 监控标的：%s\n"
                                        "- 预警条件：%s\n"
                                        "- 当前最新价：**%.1f**\n"
                                        "- 触发时间：%s\n"
                                    ) % (alert_contract, direction_txt, current_price, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                    requests.post(url, data={"title": title, "desp": desp}, timeout=5)
                            except Exception as wx_err:
                                log_error(wx_err, "AlertWeChatPush")

            if updated:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(alerts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log_error(e, "CheckPriceAlerts")

    def update_silver_board_ui(self):
        d_ag = self.silver_data
        d_au = self.gold_data
        d_xau = getattr(self, 'xau_data', {"price": "4105.58", "change_pct": "+0.89%"})
        d_xag = getattr(self, 'xag_data', {"price": "52.660", "change_pct": "+1.48%"})
        d_iau = getattr(self, 'iau_data', {"price": "76.140", "change_pct": "-2.11%"})
        d_slv = getattr(self, 'slv_data', {"price": "46.835", "change_pct": "-2.71%"})
        
        ag_chg = safe_float(d_ag.get('change', 0))
        au_chg = safe_float(d_au.get('change', 0))
        xau_chg = safe_float(d_xau.get('change', 0))
        xag_chg = safe_float(d_xag.get('change', 0))
        iau_chg = safe_float(d_iau.get('change', 0))
        slv_chg = safe_float(d_slv.get('change', 0))

        ag_color = "#ef4444" if ag_chg >= 0 else "#22c55e"
        au_color = "#ef4444" if au_chg >= 0 else "#22c55e"
        xau_color = "#ef4444" if xau_chg >= 0 else "#22c55e"
        xag_color = "#ef4444" if xag_chg >= 0 else "#22c55e"
        iau_color = "#ef4444" if iau_chg >= 0 else "#22c55e"
        slv_color = "#ef4444" if slv_chg >= 0 else "#22c55e"

        html_text = (
            '<table width="100%%" cellspacing="0" cellpadding="0" style="font-family: Consolas, monospace; background-color: #141820; border-radius: 8px; padding: 1px 2px; line-height: 0.95;">'
            '<tr>'
            '<td style="font-size: 13px; font-weight: bold; color: #ffffff; padding: 1px 4px;">沪银主力 (%s)</td>'
            '<td align="center" style="font-size: 15px; font-weight: bold; color: #ffffff; padding: 1px 4px;">%s</td>'
            '<td align="right" style="font-size: 13px; font-weight: bold; color: %s; padding: 1px 4px;">%s</td>'
            '</tr>'
            '<tr>'
            '<td style="font-size: 13px; font-weight: bold; color: #ffffff; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">沪金主力 (%s)</td>'
            '<td align="center" style="font-size: 15px; font-weight: bold; color: #ffffff; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">%s</td>'
            '<td align="right" style="font-size: 13px; font-weight: bold; color: %s; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">%s</td>'
            '</tr>'
            '<tr>'
            '<td style="font-size: 13px; font-weight: bold; color: #ffffff; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">伦敦金 (XAUUSD)</td>'
            '<td align="center" style="font-size: 15px; font-weight: bold; color: #ffffff; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">%s</td>'
            '<td align="right" style="font-size: 13px; font-weight: bold; color: %s; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">%s</td>'
            '</tr>'
            '<tr>'
            '<td style="font-size: 13px; font-weight: bold; color: #ffffff; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">伦敦银现 (AGUSDO)</td>'
            '<td align="center" style="font-size: 15px; font-weight: bold; color: #ffffff; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">%s</td>'
            '<td align="right" style="font-size: 13px; font-weight: bold; color: %s; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">%s</td>'
            '</tr>'
            '<tr>'
            '<td style="font-size: 13px; font-weight: bold; color: #ffffff; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">IAU (LBMA黄金价格ETF)</td>'
            '<td align="center" style="font-size: 15px; font-weight: bold; color: #ffffff; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">%s</td>'
            '<td align="right" style="font-size: 13px; font-weight: bold; color: %s; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">%s</td>'
            '</tr>'
            '<tr>'
            '<td style="font-size: 13px; font-weight: bold; color: #ffffff; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">SLV (LBMA白银现货ETF)</td>'
            '<td align="center" style="font-size: 15px; font-weight: bold; color: #ffffff; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">%s</td>'
            '<td align="right" style="font-size: 13px; font-weight: bold; color: %s; padding: 1px 4px; border-top: 1px solid rgba(255,255,255,0.06);">%s</td>'
            '</tr>'
            '</table>'
        ) % (
            str(self.ag_contract), str(d_ag.get("price", "12687.0")), str(ag_color), str(d_ag.get("change_pct", "+0.61%%")),
            str(self.au_contract), str(d_au.get("price", "885.5")), str(au_color), str(d_au.get("change_pct", "+0.97%%")),
            str(d_xau.get("price", "4105.58")), str(xau_color), str(d_xau.get("change_pct", "+0.89%%")),
            str(d_xag.get("price", "52.660")), str(xag_color), str(d_xag.get("change_pct", "+1.48%%")),
            str(d_iau.get("price", "76.140")), str(iau_color), str(d_iau.get("change_pct", "-2.11%%")),
            str(d_slv.get("price", "46.835")), str(slv_color), str(d_slv.get("change_pct", "-2.71%%"))
        )
        self.silver_board.setText(html_text)

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)

        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor("#38bdf8")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 24, 24)
        painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))

        tray_menu = QMenu()
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)

        alert_action = QAction("价格预警", self)
        alert_action.triggered.connect(self.open_price_alert)
        tray_menu.addAction(alert_action)

        calc_action = QAction("盈亏计算器", self)
        calc_action.triggered.connect(self.open_calculator)
        tray_menu.addAction(calc_action)

        settings_action = QAction("高级设置", self)
        settings_action.triggered.connect(self.open_settings)
        tray_menu.addAction(settings_action)

        tray_menu.addSeparator()
        quit_action = QAction("退出程序", self)
        quit_action.triggered.connect(self.real_quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setToolTip("桌面市场日历时钟 (运行中)")
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def closeEvent(self, event: QCloseEvent):
        if self.is_forced_exit:
            self.save_settings()
            event.accept()
        else:
            event.ignore()
            self.hide()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.raise_()
                self.activateWindow()

    def real_quit(self):
        self.is_forced_exit = True
        self.save_settings()
        
        for worker in [getattr(self, 'ag_worker', None), getattr(self, 'au_worker', None), getattr(self, 'xau_worker', None), getattr(self, 'xag_worker', None), getattr(self, 'iau_worker', None), getattr(self, 'slv_worker', None)]:
            if worker:
                worker.stop()
        for thread in [getattr(self, 'ag_thread', None), getattr(self, 'au_thread', None), getattr(self, 'xau_thread', None), getattr(self, 'xag_thread', None), getattr(self, 'iau_thread', None), getattr(self, 'slv_thread', None)]:
            if thread:
                thread.quit()
                thread.wait(1000)

        self.tray_icon.hide()
        QApplication.quit()

    def apply_theme(self, bg_color, time_color, card_bg, accent):
        self.current_bg_color = bg_color
        self.current_time_color = time_color
        self.current_card_bg = card_bg
        self.current_accent = accent

        self.container.setStyleSheet("QWidget#MainContainer { background-color: %s; border-radius: 12px; border: none; }" % bg_color)
        self.update_clock()

        self.time_holiday_card.setStyleSheet("QWidget { background-color: transparent; border: none; }")
        self.silver_board.setStyleSheet("QLabel { background-color: %s; border-radius: 8px; padding: 4px; border: 1px solid rgba(255,255,255,0.06); }" % card_bg)
        self.status_card.setStyleSheet("QWidget { background-color: %s; border-radius: 8px; border: 1px solid rgba(255,255,255,0.06); }" % card_bg)
        

    def toggle_dock(self):
        screen = self.screen().availableGeometry() if hasattr(self, 'screen') else QApplication.desktop().screenGeometry(self)
        screen_w = screen.width()
        if not self.is_docked:
            self.normal_geometry = self.geometry()
            docked_w = 38
            self.setGeometry(screen_w - docked_w, self.y(), docked_w, self.height())
            self.is_docked = True
            self.dock_btn.setText("▶")
        else:
            if not self.normal_geometry.isNull():
                self.setGeometry(self.normal_geometry)
            else:
                self.resize(340, 620)
            self.is_docked = False
            self.dock_btn.setText("◀")
        self.save_settings()

    def enterEvent(self, event):
        if self.is_docked:
            screen = self.screen().availableGeometry() if hasattr(self, 'screen') else QApplication.desktop().screenGeometry(self)
            screen_w = screen.width()
            full_w = self.normal_geometry.width() if not self.normal_geometry.isNull() else 340
            self.setGeometry(screen_w - full_w, self.y(), full_w, self.height())
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.is_docked:
            screen = self.screen().availableGeometry() if hasattr(self, 'screen') else QApplication.desktop().screenGeometry(self)
            screen_w = screen.width()
            docked_w = 38
            self.setGeometry(screen_w - docked_w, self.y(), docked_w, self.height())
        super().leaveEvent(event)

    def toggle_lock(self):
        self.is_locked = not self.is_locked
        if self.is_locked:
            self.lock_btn.setText("[锁]")
        else:
            self.lock_btn.setText("[开]")
        self.save_settings()

    def open_calculator(self):
        self.calc_dlg = ProfitLossCalculatorDialog(self)
        self.calc_dlg.exec_()

    def open_price_alert(self):
        dlg = PriceAlertDialog(self)
        dlg.exec_()

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec_()

    def show_calendar(self):
        dialog = MarketCalendarDialog(self)
        dialog.exec_()

    def get_market_countdown(self, now, market_type="AG"):
        t = now.time()
        weekday = now.weekday()
        
        if market_type == "AG":
            if weekday == 5 and t <= datetime.time(2, 30):
                close_dt = datetime.datetime.combine(now.date(), datetime.time(2, 30))
                diff = close_dt - now
                if diff.total_seconds() > 0:
                    s = int(diff.total_seconds())
                    return True, "贵金属期货：交易中 (Live)", f"距收盘 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            
            if weekday == 5 or weekday == 6:
                days_ahead = 2 if weekday == 5 else 1
                next_open = datetime.datetime.combine(now.date() + datetime.timedelta(days=days_ahead), datetime.time(9, 0))
                diff = next_open - now
                s = int(diff.total_seconds())
                d = s // 86400
                h = (s % 86400) // 3600
                m = (s % 3600) // 60
                return False, "贵金属期货：周末休市", f"距开盘 {d}天 {h:02d}时{m:02d}分"

            s_m_open = datetime.datetime.combine(now.date(), datetime.time(9, 0))
            s_m_rest_start = datetime.datetime.combine(now.date(), datetime.time(10, 15))
            s_m_rest_end = datetime.datetime.combine(now.date(), datetime.time(10, 30))
            s_m_close = datetime.datetime.combine(now.date(), datetime.time(11, 30))
            s_a_open = datetime.datetime.combine(now.date(), datetime.time(13, 30))
            s_a_close = datetime.datetime.combine(now.date(), datetime.time(15, 0))
            s_n_open = datetime.datetime.combine(now.date(), datetime.time(21, 0))
            s_n_close = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time(2, 30))
            
            if t <= datetime.time(2, 30):
                close_dt = datetime.datetime.combine(now.date(), datetime.time(2, 30))
                diff = close_dt - now
                s = int(diff.total_seconds())
                return True, "贵金属期货：交易中 (Live)", f"距收盘 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            elif datetime.time(2, 30) < t < datetime.time(9, 0):
                diff = s_m_open - now
                s = int(diff.total_seconds())
                return False, "贵金属期货：早盘休市", f"距开盘 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            elif datetime.time(9, 0) <= t < datetime.time(10, 15):
                diff = s_m_rest_start - now
                s = int(diff.total_seconds())
                return True, "贵金属期货：交易中 (Live)", f"距小节休息 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            elif datetime.time(10, 15) <= t < datetime.time(10, 30):
                diff = s_m_rest_end - now
                s = int(diff.total_seconds())
                return False, "贵金属期货：小节休息", f"距开盘 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            elif datetime.time(10, 30) <= t <= datetime.time(11, 30):
                diff = s_m_close - now
                s = int(diff.total_seconds())
                return True, "贵金属期货：交易中 (Live)", f"距休市 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            elif datetime.time(11, 30) < t < datetime.time(13, 30):
                diff = s_a_open - now
                s = int(diff.total_seconds())
                return False, "贵金属期货：午间休市", f"距开盘 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            elif datetime.time(13, 30) <= t <= datetime.time(15, 0):
                diff = s_a_close - now
                s = int(diff.total_seconds())
                return True, "贵金属期货：交易中 (Live)", f"距收盘 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            elif datetime.time(15, 0) < t < datetime.time(21, 0):
                diff = s_n_open - now
                s = int(diff.total_seconds())
                return False, "贵金属期货：日间休市", f"距开盘 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            elif datetime.time(21, 0) <= t <= datetime.time(23, 59, 59):
                diff = s_n_close - now
                s = int(diff.total_seconds())
                return True, "贵金属期货：交易中 (Live)", f"距收盘 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
                
        elif market_type == "A":
            if weekday >= 5:
                days_ahead = 2 if weekday == 5 else 1
                next_open = datetime.datetime.combine(now.date() + datetime.timedelta(days=days_ahead), datetime.time(9, 30))
                diff = next_open - now
                s = int(diff.total_seconds())
                d = s // 86400
                h = (s % 86400) // 3600
                m = (s % 3600) // 60
                return False, "股市：周末休市", f"距开盘 {d}天 {h:02d}时{m:02d}分"
                
            s_m_open = datetime.datetime.combine(now.date(), datetime.time(9, 30))
            s_m_close = datetime.datetime.combine(now.date(), datetime.time(11, 30))
            s_a_open = datetime.datetime.combine(now.date(), datetime.time(13, 0))
            s_a_close = datetime.datetime.combine(now.date(), datetime.time(15, 0))
            
            if t < datetime.time(9, 30):
                diff = s_m_open - now
                s = int(diff.total_seconds())
                return False, "股市：未开盘", f"距开盘 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            elif datetime.time(9, 30) <= t <= datetime.time(11, 30):
                diff = s_m_close - now
                s = int(diff.total_seconds())
                return True, "股市：交易中 (Live)", f"距午休 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            elif datetime.time(11, 30) < t < datetime.time(13, 0):
                diff = s_a_open - now
                s = int(diff.total_seconds())
                return False, "股市：午间休市", f"距开盘 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            elif datetime.time(13, 0) <= t <= datetime.time(15, 0):
                diff = s_a_close - now
                s = int(diff.total_seconds())
                return True, "股市：交易中 (Live)", f"距收盘 {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            else:
                next_open = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time(9, 30))
                diff = next_open - now
                s = int(diff.total_seconds())
                h = s // 3600
                m = (s % 3600) // 60
                return False, "股市：已收盘", f"距开盘 {h:02d}时{m:02d}分"
                
        return False, "已休市", ""

    def update_clock(self):
        now = datetime.datetime.now()
        week_days = ['星期一','星期二','星期三','星期四','星期五','星期六','星期日']
        
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%Y年%m月%d日") + " " + week_days[now.weekday()]
        self.update_next_holiday(now)
        
        html = (
            '<table width="100%%" cellspacing="0" cellpadding="0" style="margin: 0px; padding: 0px; border-collapse: collapse; line-height: 1.0;">'
            '<tr><td align="center" style="font-size: 32px; font-weight: bold; font-family: Consolas, monospace; color: #ffffff; padding: 0px; margin: 0px; border: none;">%s</td></tr>'
            '<tr><td align="center" style="font-size: 13px; font-family: sans-serif; color: %s; padding: 1px 0px 0px 0px; margin: 0px; border: none;">%s</td></tr>'
            '<tr><td align="center" style="font-size: 13px; font-weight: bold; font-family: \"Microsoft YaHei\", sans-serif; color: #ffffff; padding: 1px 0px 0px 0px; margin: 0px; border: none;"><span style="color: #ffffff;">%s</span></td></tr>'
            '</table>'
        ) % (time_str, self.current_time_color, date_str, getattr(self, 'cached_holiday_text', '距离下一节假日：元旦'))
        
        self.time_holiday_board.setText(html)
        self.update_macro_countdown(now)
        
        is_a_open, a_status, a_countdown = self.get_market_countdown(now, market_type="A")
        is_ag_open, ag_status, ag_countdown = self.get_market_countdown(now, market_type="AG")
        
        ag_cd_str = f" ({ag_countdown})" if ag_countdown else ""
        a_cd_str = f" ({a_countdown})" if a_countdown else ""
        self.stock_status_label.setText(f"{a_status}  <span style='color: #ffffff; font-size: 11px;'>{a_cd_str}</span>")
        self.silver_status_label.setText(f"{ag_status}  <span style='color: #ffffff; font-size: 11px;'>{ag_cd_str}</span>")

    def update_macro_countdown(self, now):
        upcoming = []
        macro_list = get_dynamic_macro_events()
        for ev in macro_list:
            diff = ev["time"] - now
            if diff.total_seconds() > 0:
                upcoming.append((ev, diff))
        
        upcoming.sort(key=lambda x: x[1])
        upcoming = upcoming[:3]

        if upcoming:
            rows_html = ""
            for ev, diff in upcoming:
                total_sec = int(diff.total_seconds())
                days = total_sec // 86400
                hours = (total_sec % 86400) // 3600
                mins = (total_sec % 3600) // 60
                
                if days > 0:
                    time_str = "%d天 %02d时%02d分" % (days, hours, mins)
                else:
                    time_str = "%02d时%02d分" % (hours, mins)
                
                rows_html += '<tr><td style="font-size: 11px; color: #ffffff; font-weight: bold; padding: 0px 3px; margin: 0px;">%s</td><td align="right" style="font-size: 11px; font-weight: bold; color: #ffffff; padding: 0px 3px; margin: 0px;">%s</td></tr>' % (ev["name"], time_str)

            html_text = '<table width="100%%" cellspacing="0" cellpadding="0" style="font-family: Consolas, monospace; background-color: #141820; border-radius: 6px; padding: 0px 2px; line-height: 0.75;">%s</table>' % rows_html
            self.macro_board.setText(html_text)
        else:
            self.macro_board.setText("宏观事件：暂无近期安排")

    def update_next_holiday(self, now):
        today_date = now.date()
        next_date_str = None
        next_reason = None
        days_diff = 9999

        sorted_dates = sorted(HOLIDAY_SCHEDULE.keys())
        for d_str in sorted_dates:
            d_obj = datetime.datetime.strptime(d_str, "%Y-%m-%d").date()
            if d_obj >= today_date:
                info = HOLIDAY_SCHEDULE[d_str]
                types = info.get("types", []) if isinstance(info, dict) else info
                if "A" in types or "AG" in types:
                    diff = (d_obj - today_date).days
                    next_date_str = d_str
                    next_reason = info.get("reason", "休市") if isinstance(info, dict) else "休市"
                    days_diff = diff
                    break

        if next_date_str:
            clean_reason = next_reason.replace("休市", "").replace("假期", "").strip()
            if not clean_reason:
                clean_reason = "节假日"
            self.cached_holiday_text = "距离下一节假日：%s (%d天)" % (clean_reason, days_diff)
        else:
            self.cached_holiday_text = "距离下一节假日：暂无近期安排"

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.is_locked:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.is_locked:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

if __name__ == "__main__":
    import socket
    single_instance_socket = None
    try:
        single_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        single_socket.bind(('127.0.0.1', 49832))
        single_socket.listen(1)
        single_instance_socket = single_socket
    except socket.error:
        pass

    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        window = ClockWindow()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        traceback.print_exc()
        input("Press Enter to exit...")
