# -*- coding: utf-8 -*-
import sys
import winsound
import os
import datetime
import requests
import traceback
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
from PyQt5.QtGui import QColor, QBrush, QDesktopServices, QPainter, QIcon, QPixmap, QPen, QPolygon, QPainterPath, QLinearGradient, QFont
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QCloseEvent

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
DEFAULT_AG_PRICE = 12341.0
DEFAULT_AU_PRICE = 852.50
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
    grace = datetime.timedelta(hours=2)
    def _next_or_recent(day, hour, minute):
        dt = datetime.datetime(y, m, day, hour, minute)
        if dt + grace > now:
            return dt
        ny = y + (1 if m == 12 else 0)
        nm = (m % 12) + 1
        return datetime.datetime(ny, nm, day, hour, minute)

    events = [
        {"name": "美国非农就业报告 (NFP)", "time": _next_or_recent(5, 20, 30)},
        {"name": "美联储利率决议 (FOMC)", "time": _next_or_recent(18, 14, 0)},
        {"name": "美国CPI数据公布", "time": _next_or_recent(12, 20, 30)},
        {"name": "欧洲央行利率决议", "time": _next_or_recent(15, 14, 15)}
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
    def __init__(self, current_contract="AG0", current_price=12341.0, parent=None):
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
            p = 12341.0
            if self.parent_window and hasattr(self.parent_window, 'silver_data'):
                try:
                    p = safe_float(self.parent_window.silver_data.get("price", 12341.0))
                except Exception:
                    pass
            self.price_spin.setValue(p)
            self.hint_lbl.setText("当前最新参考价: %.1f" % p)
        else:
            self.contract = getattr(self.parent_window, 'au_contract', 'AU0') if self.parent_window else "AU0"
            p = 852.50
            if self.parent_window and hasattr(self.parent_window, 'gold_data'):
                try:
                    p = safe_float(self.parent_window.gold_data.get("price", 852.50))
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
            status_str = "监控中" if alert.get("active", True) else "已平仓"
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
        curr_price = 12341.0
        if self.parent_window and hasattr(self.parent_window, 'silver_data'):
            curr_contract = self.parent_window.silver_data.get("contract", "AG0")
            try:
                curr_price = safe_float(self.parent_window.silver_data.get("price", 12341.0))
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
                            vals = line.split('="')[1].strip('"\n').split(',')
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
                            vals = line.split('="')[1].strip('"\n').split(',')
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
                    vals = [v.strip() for v in parts[1].strip('";\n').split(',')]
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
                    vals = parts[1].strip('";\n').split(',')
                    if len(vals) > 1 and safe_float(vals[0], 0) > 0:
                        price_val = safe_float(vals[0], 0)
                        settle_p = safe_float(vals[7], 0.0) if len(vals) > 7 else 0.0
                        if settle_p <= 0 and len(vals) > 8:
                            settle_p = safe_float(vals[8], 0.0)
                        
                        if settle_p > 0 and abs(price_val - settle_p) < price_val * 0.25:
                            change = price_val - settle_p
                            change_pct = (change / settle_p) * 100.0
                        else:
                            raw_chg = safe_float(vals[1], 0.0) if len(vals) > 1 else 0.0
                            if abs(raw_chg) > price_val * 0.25 or raw_chg == 0.0:
                                raw_chg = safe_float(vals[2], 0.0) if len(vals) > 2 else 0.0
                            if abs(raw_chg) > 0 and abs(raw_chg) < price_val * 0.25:
                                change = raw_chg
                                settle_p = price_val - change
                                change_pct = (change / settle_p * 100.0) if settle_p > 0 else 0.0
                            else:
                                change = 0.0
                                change_pct = 0.0
                        
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
                        raw_change = safe_float(data.get('f169', 0))
                        change = raw_change / 100.0 if abs(raw_change) > 100 else raw_change
                        raw_chg_pct = safe_float(data.get('f170', 0))
                        change_pct = raw_chg_pct / 100.0 if abs(raw_chg_pct) > 10 else raw_chg_pct
                        
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


class MacroDataWorker(QObject):
    results_fetched = pyqtSignal(dict)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.running = True
        self.cached_results = {}

    def stop(self):
        self.running = False

    def fetch_jin10_or_eastmoney(self):
        results = {}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://rili.jin10.com/"
        }
        try:
            now = datetime.datetime.now()
            for delta in [0, -1]:
                d_str = (now + datetime.timedelta(days=delta)).strftime("%Y%m%d")
                url = f"https://cdn-rili.jin10.com/data/{d_str[:4]}/{d_str[4:6]}/{d_str[6:8]}/economics.json"
                resp = requests.get(url, headers=headers, timeout=3.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        for item in data:
                            country = str(item.get("country", ""))
                            name = str(item.get("name", ""))
                            actual = item.get("actual")
                            consensus = item.get("consensus")
                            previous = item.get("previous")
                            unit = str(item.get("unit", ""))
                            if actual is not None and str(actual).strip() not in ["", "None", "null", "--"]:
                                act_str = f"{actual}{unit}"
                                exp_str = f" (预期{consensus}{unit})" if consensus not in [None, "", "None", "null"] else ""
                                if "美国" in country and ("未季调CPI年率" in name or "CPI年率" in name) and "核心" not in name:
                                    results["美国CPI数据公布"] = f"已公布: {act_str}{exp_str}"
                                elif "美国" in country and "非农就业人口" in name and "ADP" not in name:
                                    results["美国非农就业报告 (NFP)"] = f"已公布: {act_str}{exp_str}"
                                elif "美国" in country and "美联储利率决议" in name:
                                    results["美联储利率决议 (FOMC)"] = f"已公布: {act_str}{exp_str}"
                                elif "欧元区" in country and ("欧洲央行" in name and ("利率" in name or "再融资" in name)):
                                    results["欧洲央行利率决议"] = f"已公布: {act_str}{exp_str}"
        except Exception:
            pass

        try:
            em_headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"}
            url_us = "https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_ECONOMICVALUE_USA&columns=ALL&pageSize=30&sortColumns=REPORT_DATE&sortTypes=-1"
            r_us = requests.get(url_us, headers=em_headers, timeout=3.0)
            if r_us.status_code == 200:
                rows = r_us.json().get("result", {}).get("data", [])
                for row in rows:
                    ind = str(row.get("INDICATOR_NAME", ""))
                    val = row.get("VALUE")
                    r_date = str(row.get("REPORT_DATE", ""))[:10]
                    if val is not None:
                        if "美国CPI数据公布" not in results and ("CPI" in ind and "同比" in ind and "核心" not in ind):
                            results["美国CPI数据公布"] = f"最新({r_date[5:]}): {val}%"
                        elif "美国非农就业报告 (NFP)" not in results and ("非农" in ind):
                            results["美国非农就业报告 (NFP)"] = f"最新({r_date[5:]}): {val}万"
                        elif "美联储利率决议 (FOMC)" not in results and ("联邦基金" in ind or "利率" in ind):
                            results["美联储利率决议 (FOMC)"] = f"最新({r_date[5:]}): {val}%"
        except Exception:
            pass

        return results

    @pyqtSlot()
    def do_work(self):
        import time
        while self.running:
            try:
                now = datetime.datetime.now()
                events = get_dynamic_macro_events()
                near_release = False
                for ev in events:
                    diff_sec = (ev["time"] - now).total_seconds()
                    if -7200 <= diff_sec <= 600:
                        near_release = True
                        break
                res = self.fetch_jin10_or_eastmoney()
                if res:
                    self.cached_results.update(res)
                    self.results_fetched.emit(dict(self.cached_results))
            except Exception:
                near_release = False

            sleep_sec = 2.0 if near_release else 15.0
            for _ in range(int(sleep_sec * 10)):
                if not self.running:
                    break
                time.sleep(0.1)
        self.finished.emit()


class IntradayWorker(QObject):
    data_ready = pyqtSignal(dict)
    finished = pyqtSignal()

    def __init__(self, symbol_key, contract_code="", ref_pre_close=0.0, initial_price=0.0):
        super().__init__()
        self.symbol_key = symbol_key
        self.contract_code = contract_code
        self.ref_pre_close = ref_pre_close
        self.initial_price = initial_price
        self.running = True

    def stop(self):
        self.running = False

    def _validate_pre_close(self, pre_close, latest_price):
        if latest_price <= 0:
            return pre_close
        if self.ref_pre_close > 0 and abs(self.ref_pre_close - latest_price) < latest_price * 0.25:
            return self.ref_pre_close
        if pre_close > 0 and abs(pre_close - latest_price) < latest_price * 0.25:
            return pre_close
        return 0.0

    def fetch_trends(self):
        headers_em = {"Referer": "https://quote.eastmoney.com", "User-Agent": "Mozilla/5.0"}
        headers_sina = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}

        # 1. 优先尝试雅虎金融全球商品图表接口（专为伦敦金 GC=F、伦敦银 SI=F 提供全球真实分时Tick数据）
        if self.symbol_key in ("XAU", "XAG"):
            yhoo_sym = "GC=F" if self.symbol_key == "XAU" else "SI=F"
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yhoo_sym}?interval=5m&range=1d"
                resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4.0)
                if resp.status_code == 200:
                    jdata = resp.json()
                    res_arr = jdata.get("chart", {}).get("result", [])
                    if res_arr:
                        meta = res_arr[0].get("meta", {})
                        timestamps = res_arr[0].get("timestamp", [])
                        quotes = res_arr[0].get("indicators", {}).get("quote", [{}])[0]
                        closes = quotes.get("close", [])
                        
                        times, prices, avgs = [], [], []
                        cum_sum = 0.0
                        for ts, p in zip(timestamps, closes):
                            if p is not None and safe_float(p) > 0:
                                dt = datetime.datetime.fromtimestamp(ts)
                                t_str = dt.strftime("%H:%M")
                                p_val = safe_float(p)
                                times.append(t_str)
                                prices.append(p_val)
                                cum_sum += p_val
                                avgs.append(cum_sum / len(prices))
                        
                        if len(prices) >= 2:
                            prev_c = safe_float(meta.get("chartPreviousClose", 0))
                            valid_pre = self._validate_pre_close(prev_c, prices[-1])
                            if valid_pre <= 0:
                                valid_pre = prices[0]
                            return {"times": times, "prices": prices, "avgs": avgs, "pre_close": valid_pre}
            except Exception:
                pass

        # 2. 国内期货（沪银、沪金）走势获取
        secid_candidates = []
        if self.symbol_key == "AG":
            c = self.contract_code.upper() if self.contract_code else "AG0"
            secid_candidates = [f"113.{c}", "113.AG0", "113.ag0", "113.AG9999"]
        elif self.symbol_key == "AU":
            c = self.contract_code.upper() if self.contract_code else "AU0"
            secid_candidates = [f"113.{c}", "113.AU0", "113.au0", "113.AU9999"]
        elif self.symbol_key == "IAU":
            secid_candidates = ["107.IAU", "105.IAU", "106.IAU"]
        elif self.symbol_key == "SLV":
            secid_candidates = ["107.SLV", "105.SLV", "106.SLV"]

        for ndays in (1, 2):
            for secid in secid_candidates:
                try:
                    url = f"https://push2.eastmoney.com/api/qt/stock/trends2/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&iscr=1&ndays={ndays}"
                    resp = requests.get(url, headers=headers_em, timeout=3.0)
                    if resp.status_code == 200:
                        data = resp.json().get("data")
                        if data and data.get("trends"):
                            trends = data["trends"]
                            raw_pre = safe_float(data.get("preClose", 0.0))
                            times, prices, avgs = [], [], []
                            for row in trends:
                                parts = str(row).split(",")
                                if len(parts) >= 3:
                                    t_str = parts[0].split(" ")[-1] if " " in parts[0] else parts[0]
                                    p_val = safe_float(parts[2], 0.0)
                                    avg_val = safe_float(parts[7], p_val) if len(parts) > 7 else p_val
                                    if p_val > 0:
                                        times.append(t_str)
                                        prices.append(p_val)
                                        avgs.append(avg_val if avg_val > 0 else p_val)
                            if len(prices) >= 2:
                                valid_pre = self._validate_pre_close(raw_pre, prices[-1])
                                if valid_pre <= 0:
                                    valid_pre = prices[0]
                                return {"times": times, "prices": prices, "avgs": avgs, "pre_close": valid_pre}
                except Exception:
                    continue

        # 3. 新浪期货分时网关兜底
        try:
            if self.symbol_key in ("AG", "AU"):
                sym = (self.contract_code if self.contract_code else f"{self.symbol_key}0").upper()
                url = f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20t1=/InnerFuturesNewService.getMinLine?symbol={sym}"
                r = requests.get(url, headers=headers_sina, timeout=3.0)
                if r.status_code == 200 and "([" in r.text:
                    raw_json = r.text.split("([", 1)[1].rsplit("])", 1)[0]
                    arr = json.loads("[" + raw_json + "]")
                    times, prices, avgs = [], [], []
                    for item in arr:
                        if isinstance(item, list) and len(item) >= 3:
                            times.append(str(item[0]))
                            p = safe_float(item[1], 0.0)
                            a = safe_float(item[2], p)
                            if p > 0:
                                prices.append(p)
                                avgs.append(a if a > 0 else p)
                    if len(prices) >= 2:
                        valid_pre = self._validate_pre_close(0.0, prices[-1])
                        if valid_pre <= 0:
                            valid_pre = prices[0]
                        return {"times": times, "prices": prices, "avgs": avgs, "pre_close": valid_pre}
        except Exception:
            pass

        return {"status": "empty"}

    @pyqtSlot()
    def do_work(self):
        import time
        last_valid_data = None
        while self.running:
            try:
                res = self.fetch_trends()
                if res and res.get("status") != "empty" and res.get("prices"):
                    last_valid_data = res
                    self.data_ready.emit(res)
                elif last_valid_data is not None:
                    self.data_ready.emit(last_valid_data)
                else:
                    self.data_ready.emit({"status": "empty"})
            except Exception:
                if last_valid_data is not None:
                    self.data_ready.emit(last_valid_data)
            
            for _ in range(30):
                if not self.running:
                    break
                time.sleep(0.1)
        self.finished.emit()


class IntradayChartCanvas(QWidget):
    def __init__(self, decimals=2, parent=None):
        super().__init__(parent)
        self.decimals = decimals
        self.times = []
        self.prices = []
        self.avgs = []
        self.pre_close = 0.0
        self.empty_msg = "正在从全球行情接口加载真实分时走势..."
        self.hover_idx = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(210)

    def set_data(self, times, prices, avgs, pre_close):
        self.times = times
        self.prices = prices
        self.avgs = avgs
        self.pre_close = pre_close
        self.update()

    def set_empty_message(self, msg):
        self.empty_msg = msg
        self.update()

    def mouseMoveEvent(self, event):
        if not self.prices:
            return
        left_m, right_m = 56, 14
        plot_w = max(1, self.width() - left_m - right_m)
        x = event.pos().x()
        if left_m <= x <= self.width() - right_m and len(self.prices) > 1:
            ratio = (x - left_m) / float(plot_w)
            idx = int(round(ratio * (len(self.prices) - 1)))
            idx = max(0, min(len(self.prices) - 1, idx))
            if idx != self.hover_idx:
                self.hover_idx = idx
                self.update()
        else:
            if self.hover_idx != -1:
                self.hover_idx = -1
                self.update()

    def leaveEvent(self, event):
        self.hover_idx = -1
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        painter.fillRect(rect, QColor("#141820"))

        left_m, right_m, top_m, bot_m = 58, 14, 24, 24
        plot_w = rect.width() - left_m - right_m
        plot_h = rect.height() - top_m - bot_m

        if plot_w <= 10 or plot_h <= 10:
            return

        painter.setPen(QPen(QColor(255, 255, 255, 25), 1))
        painter.drawRect(left_m, top_m, plot_w, plot_h)

        if len(self.prices) < 2:
            painter.setPen(QColor("#94a3b8"))
            painter.setFont(QFont("Microsoft YaHei", 10))
            painter.drawText(rect, Qt.AlignCenter, self.empty_msg)
            return

        all_vals = list(self.prices) + list(self.avgs)
        latest_p = self.prices[-1]
        use_pre = (self.pre_close > 0 and abs(self.pre_close - latest_p) < latest_p * 0.25)
        if use_pre:
            all_vals.append(self.pre_close)
        max_v = max(all_vals)
        min_v = min(all_vals)

        if use_pre:
            half_span = max(abs(max_v - self.pre_close), abs(self.pre_close - min_v))
            if half_span == 0:
                half_span = self.pre_close * 0.005
            half_span *= 1.12
            top_v = self.pre_close + half_span
            bot_v = self.pre_close - half_span
        else:
            span = max_v - min_v if max_v > min_v else max(latest_p * 0.005, 0.01)
            top_v = max_v + span * 0.1
            bot_v = min_v - span * 0.1

        v_range = max(1e-6, top_v - bot_v)

        def val_to_y(v):
            return top_m + (top_v - v) / v_range * plot_h

        def idx_to_x(i):
            return left_m + (i / float(len(self.prices) - 1)) * plot_w

        font_axis = QFont("Consolas", 8)
        painter.setFont(font_axis)
        fmt = f"%.{self.decimals}f"

        for step in range(5):
            gy = top_m + (step / 4.0) * plot_h
            gv = top_v - (step / 4.0) * v_range
            if step == 2 and use_pre:
                pen = QPen(QColor("#64748b"), 1, Qt.DashLine)
            else:
                pen = QPen(QColor(255, 255, 255, 18), 1, Qt.DotLine)
            painter.setPen(pen)
            painter.drawLine(int(left_m), int(gy), int(left_m + plot_w), int(gy))

            if use_pre:
                if gv > self.pre_close + 1e-6:
                    lbl_color = QColor("#ef4444")
                elif gv < self.pre_close - 1e-6:
                    lbl_color = QColor("#22c55e")
                else:
                    lbl_color = QColor("#cbd5e1")
            else:
                lbl_color = QColor("#94a3b8")
            painter.setPen(lbl_color)
            painter.drawText(2, int(gy - 7), left_m - 6, 14, Qt.AlignRight | Qt.AlignVCenter, fmt % gv)

        n = len(self.times)
        target_labels = ["07:00", "10:00", "13:00", "16:00", "19:00", "22:00", "01:00", "04:00"]
        drawn_x = []
        for ti, t_val in enumerate(self.times):
            if t_val in target_labels:
                tx = idx_to_x(ti)
                too_close = any(abs(tx - dx) < 40 for dx in drawn_x)
                if not too_close:
                    drawn_x.append(tx)
                    painter.setPen(QPen(QColor(255, 255, 255, 18), 1, Qt.DotLine))
                    painter.drawLine(int(tx), int(top_m), int(tx), int(top_m + plot_h))
                    painter.setPen(QColor("#94a3b8"))
                    align = Qt.AlignLeft if ti == 0 else (Qt.AlignRight if ti >= n - 2 else Qt.AlignCenter)
                    painter.drawText(int(tx - 24), int(top_m + plot_h + 4), 48, 16, align, t_val)

        price_path = QPainterPath()
        fill_path = QPainterPath()
        first_x, first_y = idx_to_x(0), val_to_y(self.prices[0])
        price_path.moveTo(first_x, first_y)
        fill_path.moveTo(first_x, top_m + plot_h)
        fill_path.lineTo(first_x, first_y)

        for i in range(1, n):
            px, py = idx_to_x(i), val_to_y(self.prices[i])
            price_path.lineTo(px, py)
            fill_path.lineTo(px, py)

        last_x = idx_to_x(n - 1)
        fill_path.lineTo(last_x, top_m + plot_h)
        fill_path.closeSubpath()

        grad = QLinearGradient(0, top_m, 0, top_m + plot_h)
        grad.setColorAt(0.0, QColor(56, 189, 248, 65))
        grad.setColorAt(1.0, QColor(56, 189, 248, 4))
        painter.fillPath(fill_path, QBrush(grad))

        if len(self.avgs) == n:
            avg_path = QPainterPath()
            avg_path.moveTo(idx_to_x(0), val_to_y(self.avgs[0]))
            for i in range(1, n):
                avg_path.lineTo(idx_to_x(i), val_to_y(self.avgs[i]))
            painter.setPen(QPen(QColor("#facc15"), 1.2))
            painter.drawPath(avg_path)

        painter.setPen(QPen(QColor("#38bdf8"), 1.8))
        painter.drawPath(price_path)

        last_y = val_to_y(self.prices[-1])
        painter.setBrush(QBrush(QColor("#38bdf8")))
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.drawEllipse(QRectF(last_x - 3, last_y - 3, 6, 6))

        if 0 <= self.hover_idx < n:
            hx = idx_to_x(self.hover_idx)
            hy = val_to_y(self.prices[self.hover_idx])
            hp = self.prices[self.hover_idx]
            ht = self.times[self.hover_idx]
            painter.setPen(QPen(QColor(255, 255, 255, 110), 1, Qt.DashLine))
            painter.drawLine(int(hx), int(top_m), int(hx), int(top_m + plot_h))
            painter.drawLine(int(left_m), int(hy), int(left_m + plot_w), int(hy))

            chg_s = ""
            if use_pre:
                pct = (hp - self.pre_close) / self.pre_close * 100.0
                if abs(pct) < 25.0:
                    chg_s = f" ({pct:+.2f}%)"
            tip_text = f"时间:{ht}  价格:{fmt % hp}{chg_s}"
            painter.setPen(QColor("#f8fafc"))
            painter.setFont(QFont("Consolas", 9, QFont.Bold))
            painter.drawText(left_m + 4, 4, plot_w - 8, 18, Qt.AlignLeft | Qt.AlignVCenter, tip_text)
        else:
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.setPen(QColor("#38bdf8"))
            painter.drawText(left_m + 4, 4, 70, 18, Qt.AlignLeft | Qt.AlignVCenter, "━ 分时价")
            painter.setPen(QColor("#facc15"))
            painter.drawText(left_m + 62, 4, 70, 18, Qt.AlignLeft | Qt.AlignVCenter, "━ 均价线")
            if use_pre:
                painter.setPen(QColor("#94a3b8"))
                painter.drawText(left_m + 120, 4, plot_w - 124, 18, Qt.AlignRight | Qt.AlignVCenter, f"昨收:{fmt % self.pre_close}")


class IntradayChartDialog(QDialog):
    def __init__(self, symbol_key, display_name, contract_code="", initial_quote=None, parent=None):
        super().__init__(parent)
        self.symbol_key = symbol_key
        self.display_name = display_name
        self.contract_code = contract_code
        self.initial_quote = initial_quote or {}
        self.drag_pos = QPoint()

        p_val = safe_float(self.initial_quote.get("price", 0.0), 0.0)
        c_val = safe_float(self.initial_quote.get("change", 0.0), 0.0)
        self.initial_price = p_val
        self.ref_pre_close = (p_val - c_val) if (p_val > 0 and abs(c_val) < p_val * 0.25) else 0.0

        self.decimals = 1 if symbol_key == "AG" else (2 if symbol_key in ("AU", "XAU") else 3)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(440, 310)
        self.init_ui()
        self.start_worker()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        box = QWidget(self)
        box.setStyleSheet("""
            QWidget {
                background-color: #1e222b;
                border-radius: 10px;
                border: 1px solid rgba(56, 189, 248, 0.35);
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setColor(QColor(0, 0, 0, 190))
        shadow.setOffset(0, 4)
        box.setGraphicsEffect(shadow)
        outer.addWidget(box)

        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title_txt = f"{self.display_name}" + (f" ({self.contract_code})" if self.contract_code and self.contract_code not in self.display_name else "")
        self.title_lbl = QLabel(title_txt)
        self.title_lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; border: none; background: transparent;")

        p_init = str(self.initial_quote.get("price", "--"))
        chg_init = str(self.initial_quote.get("change_pct", ""))
        chg_val = safe_float(self.initial_quote.get("change", 0))
        c_hex = "#ef4444" if chg_val >= 0 else "#22c55e"

        self.quote_lbl = QLabel(f"{p_init}  {chg_init}")
        self.quote_lbl.setStyleSheet(f"