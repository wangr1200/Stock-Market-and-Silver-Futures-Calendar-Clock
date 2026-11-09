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

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".market_clock_cache")

# ===== 全局配置中心 (Configuration Center) =====
now_dt = datetime.datetime.now()
yy = now_dt.year % 100
mm = now_dt.month
DEFAULT_AG_CONTRACT = "沪银2702"
DEFAULT_AU_CONTRACT = "沪金2702"
DEFAULT_AG_PRICE = 12625.0  
DEFAULT_AU_PRICE = 885.56
DEFAULT_AG_MULTIPLIER = 15.0
DEFAULT_AU_MULTIPLIER = 1000.0


# ===== 统一日志管理函数 =====
LOG_FILE = os.path.join(CACHE_DIR, "error.log")

def log_error(err, context_msg=""):
    """统一错误日志记录函数"""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 5 * 1024 * 1024:
            bak_file = os.path.join(CACHE_DIR, "error.log.bak")
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
        if not os.path.exists(CACHE_DIR):
            return
            
        now_ts = datetime.datetime.now().timestamp()
        expire_seconds = 30 * 24 * 3600  
        
        for filename in os.listdir(CACHE_DIR):
            filepath = os.path.join(CACHE_DIR, filename)
            if os.path.isfile(filepath) and not filename.endswith("error.log"):
                file_mtime = os.path.getmtime(filepath)
                if now_ts - file_mtime > expire_seconds:
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
    except Exception as e:
        log_error(e, "CleanupCache")


def check_is_market_open(now=None, market_type="AG"):
    if now is None:
        now = datetime.datetime.now()
    weekday = now.weekday()
    t = now.time()
    
    if weekday == 5 and t <= datetime.time(2, 30) and market_type == "AG":
        return True
    if weekday >= 5:
        return False
        
    date_key = now.strftime("%Y-%m-%d")
    if date_key in HOLIDAY_SCHEDULE:
        info = HOLIDAY_SCHEDULE[date_key]
        market_hours = info.get("market_hours", {})
        
        if market_type in market_hours:
            intervals = market_hours[market_type]
            for itv in intervals:
                o_h, o_m = map(int, itv["open"].split(":"))
                c_h, c_m = map(int, itv["close"].split(":"))
                if datetime.time(o_h, o_m) <= t <= datetime.time(c_h, c_m):
                    return True
            return False

        types = info.get("types", []) if isinstance(info, dict) else info
        if market_type in types:
            return False

    if market_type in ["AG", "AU"]:
        if (datetime.time(9, 0) <= t <= datetime.time(11, 30)) or \
           (datetime.time(13, 30) <= t <= datetime.time(15, 0)) or \
           (t >= datetime.time(21, 0) or t <= datetime.time(2, 30)):
            return True
    elif market_type == "A":
        if (datetime.time(9, 30) <= t <= datetime.time(11, 30)) or \
           (datetime.time(13, 0) <= t <= datetime.time(15, 0)):
            return True
    elif market_type == "HK":
        if (datetime.time(9, 30) <= t <= datetime.time(12, 0)) or \
           (datetime.time(13, 0) <= t <= datetime.time(16, 0)):
            return True
        
    return False

REG_PATH = "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
APP_NAME = "MarketDesktopClock"

def set_autostart(enable=True):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            app_path = os.path.abspath(sys.argv[0])
            if app_path.endswith(".py"):
                cmd = '"%s" "%s"' % (sys.executable, app_path)
            else:
                cmd = '"%s"' % app_path
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print("设置开机自启失败: %s" % e)
        return False

def check_autostart():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False

COLOR_THEMES = {
    "天蓝色 (默认极客)": {
        "bg_color": "#1e222b",
        "time_color": "#38bdf8",
        "card_bg": "#262b36",
        "accent": "#0284c7"
    },
    "炫酷暗黑 (Cool Black)": {
        "bg_color": "#121212",
        "time_color": "#f43f5e",
        "card_bg": "#1e1e1e",
        "accent": "#e11d48"
    },
    "翡翠森林 (Emerald Green)": {
        "bg_color": "#064e3b",
        "time_color": "#34d399",
        "card_bg": "#047857",
        "accent": "#059669"
    },
    "紫罗兰 (Midnight Violet)": {
        "bg_color": "#2e1065",
        "time_color": "#c084fc",
        "card_bg": "#3b0764",
        "accent": "#9333ea"
    },
    "浪漫樱粉 (Sakura Pink)": {
        "bg_color": "#831843",
        "time_color": "#f472b6",
        "card_bg": "#9d174d",
        "accent": "#db2777"
    },
    "琥珀烫金 (Warm Amber)": {
        "bg_color": "#451a03",
        "time_color": "#fbbf24",
        "card_bg": "#78350f",
        "accent": "#d97706"
    }
}

MACRO_EVENTS = [
    {"name": "10月 CPI数据 (11/12公布)", "time": datetime.datetime(2026, 11, 12, 21, 30)},
    {"name": "11月 非农报告 (12/04公布)", "time": datetime.datetime(2026, 12, 4, 21, 30)},
    {"name": "12月 FOMC 议息会议 (12/10)", "time": datetime.datetime(2026, 12, 10, 3, 0)},
    {"name": "11月 CPI数据 (12/10公布)", "time": datetime.datetime(2026, 12, 10, 21, 30)},
    {"name": "12月 非农报告 (01/08公布)", "time": datetime.datetime(2027, 1, 8, 21, 30)},
    {"name": "2027年1月 议息会议 (01/28)", "time": datetime.datetime(2027, 1, 28, 3, 0)},
]

HOLIDAY_SCHEDULE = {
    "2026-01-01": {"types": ["A", "HK", "AG", "AU"], "reason": "元旦休市"},
    "2026-01-02": {"types": ["A", "HK", "AG", "AU"], "reason": "元旦假期休市"},
    "2026-02-16": {"types": ["A", "HK", "AG", "AU"], "reason": "春节假期休市"},
    "2026-02-17": {"types": ["A", "HK", "AG", "AU"], "reason": "春节假期休市"},
    "2026-02-18": {"types": ["A", "HK", "AG", "AU"], "reason": "春节假期休市"},
    "2026-02-19": {"types": ["A", "HK", "AG", "AU"], "reason": "春节假期休市"},
    "2026-02-20": {"types": ["A", "AG", "AU"], "reason": "春节假期休市"},
    "2026-02-23": {"types": ["A", "AG", "AU"], "reason": "春节假期休市"},
    "2026-04-06": {"types": ["A", "HK", "AG", "AU"], "reason": "清明节休市"},
    "2026-05-01": {"types": ["A", "HK", "AG", "AU"], "reason": "劳动节休市"},
    "2026-05-04": {"types": ["A", "AG", "AU"], "reason": "劳动节假期休市"},
    "2026-05-05": {"types": ["A", "AG", "AU"], "reason": "劳动节假期休市"},
    "2026-05-25": {"types": ["HK"], "reason": "佛诞日休市（港股）"},
    "2026-06-19": {"types": ["A", "HK", "AG", "AU"], "reason": "端午节休市"},
    "2026-07-01": {"types": ["HK"], "reason": "香港特别行政区成立纪念日休市（港股）"},
    "2026-09-25": {"types": ["A", "AG", "AU"], "reason": "中秋节休市"},
    "2026-09-28": {"types": ["HK"], "reason": "中秋节翌日休市（港股）"},
    "2026-10-01": {"types": ["A", "HK", "AG", "AU"], "reason": "国庆节休市"},
    "2026-10-02": {"types": ["A", "HK", "AG", "AU"], "reason": "国庆节假期休市"},
    "2026-10-05": {"types": ["A", "AG", "AU"], "reason": "国庆节假期休市"},
    "2026-10-06": {"types": ["A", "AG", "AU"], "reason": "国庆节假期休市"},
    "2026-10-07": {"types": ["A", "AG", "AU"], "reason": "国庆节假期休市"},
    "2026-10-19": {"types": ["HK"], "reason": "重阳节休市（港股）"},
    "2026-12-25": {"types": ["HK"], "reason": "圣诞节休市（港股）"},

    "2027-01-01": {"types": ["A", "HK", "AG", "AU"], "reason": "元旦休市"},
    "2027-02-05": {
        "types": ["A", "HK", "AG", "AU"], 
        "reason": "A股/贵金属休市；港股农历新年前夕半日市（12:00收市）",
        "market_hours": {
            "HK": [{"open": "09:30", "close": "12:00"}]
        }
    },
    "2027-02-08": {"types": ["A", "HK", "AG", "AU"], "reason": "春节假期休市（农历年初三）"},
    "2027-02-09": {"types": ["A", "HK", "AG", "AU"], "reason": "春节假期休市（农历年初四）"},
    "2027-02-10": {"types": ["A", "AG", "AU"], "reason": "春节假期休市"},
    "2027-02-11": {"types": ["A", "AG", "AU"], "reason": "春节假期休市"},
    "2027-02-12": {"types": ["A", "AG", "AU"], "reason": "春节假期休市"},
    "2027-03-26": {"types": ["HK"], "reason": "耶稣受难节休市（港股）"},
    "2027-03-29": {"types": ["HK"], "reason": "复活节周一休市（港股）"},
    "2027-04-05": {"types": ["A", "HK", "AG", "AU"], "reason": "清明节休市"},
    "2027-05-03": {"types": ["A", "AG", "AU"], "reason": "劳动节假期休市"},
    "2027-05-04": {"types": ["A", "AG", "AU"], "reason": "劳动节假期休市"},
    "2027-05-05": {"types": ["A", "AG", "AU"], "reason": "劳动节假期休市"},
    "2027-05-13": {"types": ["HK"], "reason": "佛诞休市（港股）"},
    "2027-06-09": {"types": ["A", "HK", "AG", "AU"], "reason": "端午节休市"},
    "2027-07-01": {"types": ["HK"], "reason": "香港特别行政区成立纪念日休市（港股）"},
    "2027-09-15": {"types": ["A", "AG", "AU"], "reason": "中秋节休市（A股/贵金属）"},
    "2027-09-16": {"types": ["HK"], "reason": "中秋节翌日休市（港股）"},
    "2027-10-01": {"types": ["A", "HK", "AG", "AU"], "reason": "国庆日休市"},
    "2027-10-04": {"types": ["A", "AG", "AU"], "reason": "国庆节假期休市"},
    "2027-10-05": {"types": ["A", "AG", "AU"], "reason": "国庆节假期休市"},
    "2027-10-06": {"types": ["A", "AG", "AU"], "reason": "国庆节假期休市"},
    "2027-10-07": {"types": ["A", "AG", "AU"], "reason": "国庆节假期休市"},
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
        title_lbl.setStyleSheet("color: #38bdf8; font-size: 15px; font-weight: bold; border: none; background: transparent;")
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
    def __init__(self, current_contract="沪银2702", current_price=12625.0, parent=None):
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
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8; margin-bottom: 6px;")
        layout.addWidget(title)

        form = QFormLayout()

        self.contract_combo = QComboBox()
        ag_c = getattr(self.parent_window, 'ag_contract', '沪银2702') if self.parent_window else "沪银2702"
        au_c = getattr(self.parent_window, 'au_contract', '沪金2702') if self.parent_window else "沪金2702"
        self.contract_combo.addItems([ag_c, au_c])
        if "AU" in self.default_contract.upper() or "沪金" in self.default_contract:
            self.contract_combo.setCurrentIndex(1)
        else:
            self.contract_combo.setCurrentIndex(0)
            
        self.contract_combo.setStyleSheet("""
            QComboBox {
                background-color: #262b36; color: #38bdf8; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 12px;
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
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 12px;
            }
            QComboBox QAbstractItemView { background-color: #1e222b; color: white; selection-background-color: #0284c7; }
        """)
        form.addRow("预警条件:", self.cond_combo)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(1.0, 999999.0)
        self.price_spin.setDecimals(2)
        self.price_spin.setValue(self.current_price)
        self.price_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #262b36; color: #38bdf8; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;
            }
        """)
        form.addRow("目标价格:", self.price_spin)

        layout.addLayout(form)

        self.hint_lbl = QLabel("当前最新参考价: %.2f" % self.current_price)
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
            self.contract = getattr(self.parent_window, 'ag_contract', '沪银2702') if self.parent_window else "沪银2702"
            p = 12625.0
            if self.parent_window and hasattr(self.parent_window, 'silver_data'):
                try:
                    p = float(self.parent_window.silver_data.get("price", 12625.0))
                except Exception:
                    pass
            self.price_spin.setValue(p)
            self.hint_lbl.setText("当前最新参考价: %.2f" % p)
        else:
            self.contract = getattr(self.parent_window, 'au_contract', '沪金2702') if self.parent_window else "沪金2702"
            p = 885.56
            if self.parent_window and hasattr(self.parent_window, 'gold_data'):
                try:
                    p = float(self.parent_window.gold_data.get("price", 885.56))
                except Exception:
                    pass
            self.price_spin.setValue(p)
            self.hint_lbl.setText("当前最新参考价: %.2f" % p)

    def on_ok(self):
        idx = self.contract_combo.currentIndex()
        if idx == 0:
            self.contract = getattr(self.parent_window, 'ag_contract', '沪银2702') if self.parent_window else "沪银2702"
        else:
            self.contract = getattr(self.parent_window, 'au_contract', '沪金2702') if self.parent_window else "沪金2702"
            
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
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        top_row.addWidget(title)
        top_row.addStretch()

        add_btn = QPushButton("+ 添加预警")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7; color: white; border-radius: 4px; padding: 5px 12px; font-weight: bold; font-size: 12px;
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
                gridline-color: #262b36; font-size: 12px;
            }
            QHeaderView::section {
                background-color: #262b36; color: #38bdf8; font-weight: bold; border: none; padding: 4px;
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
                background-color: #059669; color: white; border-radius: 4px; padding: 5px 12px; font-weight: bold; font-size: 12px;
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
        os.makedirs(CACHE_DIR, exist_ok=True)
        return os.path.join(CACHE_DIR, "price_alerts.json")

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
            price_item = QTableWidgetItem("%.2f" % alert.get('target', 0.0))
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
        curr_contract = "沪银2702"
        curr_price = 12625.0
        if self.parent_window and hasattr(self.parent_window, 'silver_data'):
            curr_contract = self.parent_window.silver_data.get("contract", "沪银2702")
            try:
                curr_price = float(self.parent_window.silver_data.get("price", 12625.0))
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
                    res_add = subprocess.run(["git", "add", "price_alerts.json"], cwd=repo_dir, capture_output=True, text=True)
                    if res_add.returncode == 0:
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
                alerts_summary += "- %d. **%s** | %s **%.2f** | %s\n" % (idx+1, c_name, c_type, c_target, status)

            if not alerts_summary:
                alerts_summary = "暂无活跃预警"

            server_key = os.getenv("SERVER_CHAN_KEY", "")
            if not server_key:
                try:
                    config_file = os.path.join(CACHE_DIR, "config.json")
                    if os.path.exists(config_file):
                        with open(config_file, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                            server_key = cfg.get("server_chan_key", "") or cfg.get("server_key", "")
                except Exception:
                    pass
            url = "https://sctapi.ftqq.com/%s.send" % server_key if server_key else ""
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            title = "[桌面时钟] 预警配置已同步更新"
            desp = (
                "### 本地新预警已成功同步！\n"
                "- **同步时间**：%s\n"
                "- **当前预警总数**：%d 条\n\n"
                "**当前所有预警列表**：\n%s\n"
                "> 云端监控进程将在下一轮（60秒内）自动应用最新规则。"
            ) % (now_str, len(alerts), alerts_summary)
            if server_key:
                try:
                    r = requests.post(url, data={"title": title, "desp": desp}, timeout=5)
                    log_error("ServerChan response: %s %s" % (r.status_code, r.text), "ServerChanSync")
                except Exception as sc_err:
                    log_error(sc_err, "ServerChanRequest")
            else:
                log_error("Server key is empty!", "ServerChanSync")

            dlg = SilentTipDialog(
                "云端同步与微信提醒成功", 
                "最新的价格预警配置已成功处理，并已通过微信发送了同步通知！", 
                self
            )
            dlg.exec_()
        except Exception as e:
            dlg = SilentTipDialog("同步失败", "推送或发送微信通知失败：%s" % str(e), self)
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
                "AG": QColor("#38bdf8"),
                "AU": QColor("#facc15")
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
                font-size: 14px;
                color: #334155;
                selection-background-color: #3b82f6;
                selection-color: white;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #1e222b;
            }
            QCalendarWidget QToolButton {
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
        """)
        self.calendar.clicked.connect(self.on_date_clicked)
        layout.addWidget(self.calendar)

        legend_label = QLabel("A股休市  |  港股休市  |  贵金属期货休市")
        legend_label.setStyleSheet("color: #475569; font-size: 12px; font-weight: bold; margin-top: 6px;")
        layout.addWidget(legend_label)

        hint_label = QLabel("点击带圆点的日期可查看具体休市原因")
        hint_label.setStyleSheet("color: #64748b; font-size: 12px; font-weight: bold; padding: 4px;")
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
            if "AG" in types or "AU" in types: type_desc.append("贵金属期货")
            
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
        title = QLabel("桌面时钟设置与健康提醒")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8; margin-bottom: 6px;")
        layout.addWidget(title)

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

        sep_lbl = QLabel("─── 健康生活提醒 ───")
        sep_lbl.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: bold; margin-top: 4px;")
        form_layout.addRow(sep_lbl)

        self.water_chk = QCheckBox("启用喝水提醒")
        self.water_chk.setChecked(getattr(self.parent_window, 'water_enabled', True))
        self.water_chk.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        form_layout.addRow(self.water_chk)

        self.water_spin = QSpinBox()
        self.water_spin.setRange(10, 240)
        self.water_spin.setValue(getattr(self.parent_window, 'water_interval_min', 45))
        self.water_spin.setSuffix(" 分钟")
        self.water_spin.setStyleSheet("""
            QSpinBox { background-color: #262b36; color: #38bdf8; font-weight: bold; border: 1px solid #475569; border-radius: 4px; padding: 3px; }
        """)
        form_layout.addRow("喝水提醒间隔:", self.water_spin)

        self.sport_chk = QCheckBox("启用久坐运动提醒")
        self.sport_chk.setChecked(getattr(self.parent_window, 'sport_enabled', True))
        self.sport_chk.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        form_layout.addRow(self.sport_chk)

        self.sport_spin = QSpinBox()
        self.sport_spin.setRange(15, 360)
        self.sport_spin.setValue(getattr(self.parent_window, 'sport_interval_min', 90))
        self.sport_spin.setSuffix(" 分钟")
        self.sport_spin.setStyleSheet("""
            QSpinBox { background-color: #262b36; color: #38bdf8; font-weight: bold; border: 1px solid #475569; border-radius: 4px; padding: 3px; }
        """)
        form_layout.addRow("久坐提醒间隔:", self.sport_spin)

        sep_lbl2 = QLabel("─── 个性化外观 ───")
        sep_lbl2.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: bold; margin-top: 4px;")
        form_layout.addRow(sep_lbl2)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(COLOR_THEMES.keys()) + ["自定义数字颜色..."])
        settings_file = os.path.join(CACHE_DIR, "config.json")
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
                background-color: #262b36; color: #e2e8f0; border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 12px;
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
        settings_file = os.path.join(CACHE_DIR, "config.json")
        data = {}
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        data["theme_index"] = index
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
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
            color = QColorDialog.getColor(QColor(self.parent_window.current_time_color), self, "选择自定义数字显示颜色")
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
            self.parent_window.water_enabled = self.water_chk.isChecked()
            self.parent_window.water_interval_min = self.water_spin.value()
            self.parent_window.sport_enabled = self.sport_chk.isChecked()
            self.parent_window.sport_interval_min = self.sport_spin.value()
            
            self.parent_window.update_health_timers()
            self.parent_window.save_settings()
        self.accept()


class BaseQuoteSource:
    def get_quote(self, target_type: str) -> dict:
        raise NotImplementedError


class SinaQuoteSource(BaseQuoteSource):
    def get_quote(self, target_type: str) -> dict:
        import time
        now = datetime.datetime.now()
        prefix = "AG" if target_type == "沪银" else "AU"
        headers = {
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        timestamp = int(time.time() * 1000)
        prefix_lower = prefix.lower()
        symbols = ["nf_%s0" % prefix, "nf_%s0" % prefix_lower]
        for i in range(12):
            target_m = now.month + i
            target_y = now.year % 100
            if target_m > 12:
                target_m -= 12
                target_y += 1
            code_str = "nf_%s%02d%02d" % (prefix, target_y, target_m)
            symbols.append(code_str)
            symbols.append(code_str.lower())
        symbols = list(dict.fromkeys(symbols))

        url = "https://hq.sinajs.cn/list=%s&_t=%d" % (','.join(symbols), timestamp)
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200:
            for line in resp.text.split(';'):
                if 'hq_str_nf_' in line and '="' in line:
                    parts_split = line.split('="')
                    if len(parts_split) > 1:
                        data_str = parts_split[1].strip('"')
                        if data_str and len(data_str.split(',')) > 13:
                            parts = data_str.split(',')
                            
                            # 映射为同花顺风格的中文合约名 (如 沪金2702 / 沪银2702)
                            raw_code = parts[12] if len(parts) > 12 and parts[12] else ("ag2702" if prefix == "AG" else "au2702")
                            clean_code = raw_code.lower()
                            chinese_name = "沪银" if prefix == "AG" else "沪金"
                            if "2702" in clean_code:
                                display_contract = "%s2702" % chinese_name
                            else:
                                display_contract = "%s%s" % (chinese_name, clean_code[2:] if len(clean_code) > 2 else "2702")

                            fallback_p = 12625.0 if prefix == "AG" else 885.56
                            latest = float(parts[8]) if len(parts) > 8 and parts[8] else float(parts[2]) if len(parts) > 2 and parts[2] else fallback_p
                            
                            # 正确取新浪期货接口的昨结算价 (parts[7])
                            pre_settle = float(parts[7]) if len(parts) > 7 and parts[7] else latest
                            change = latest - pre_settle
                            change_pct = (change / pre_settle * 100) if pre_settle > 0 else 0.0
                            
                            volume = parts[11] if len(parts) > 11 else "0"
                            open_interest = parts[10] if len(parts) > 10 else "0"
                            
                            price_fmt = "%.2f" if prefix == "AU" else "%.0f"

                            try:
                                bid1_p = float(parts[4]) if len(parts) > 4 and parts[4] else latest - 1.0
                                ask1_p = float(parts[5]) if len(parts) > 5 and parts[5] else latest + 1.0
                                bid1_v = str(parts[9]) if len(parts) > 9 and parts[9] else "1"
                                ask1_v = str(parts[10]) if len(parts) > 10 and parts[10] else "1"
                            except Exception:
                                bid1_p = latest - 1.0
                                ask1_p = latest + 1.0
                                bid1_v = "1"
                                ask1_v = "1"

                            return {
                                "contract": display_contract,
                                "price": price_fmt % latest,
                                "change": ("%+.2f" if prefix == "AU" else "%+.0f") % change,
                                "change_pct": "%+.2f%%" % change_pct,
                                "volume": volume,
                                "open_interest": open_interest,
                                "bid1_p": price_fmt % bid1_p,
                                "bid1_v": str(bid1_v),
                                "ask1_p": price_fmt % ask1_p,
                                "ask1_v": str(ask1_v)
                            }
        raise ValueError("Sina quote fetch failed")


class TencentQuoteSource(BaseQuoteSource):
    def get_quote(self, target_type: str) -> dict:
        prefix = "AG" if target_type == "沪银" else "AU"
        t_sym = "f_%s2702" % prefix.lower()
        url = "https://qt.gtimg.cn/q=%s" % t_sym
        headers = {"Referer": "https://finance.qq.com", "User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200 and 'v_' in resp.text:
            parts = resp.text.split('"')[1].split('~')
            if len(parts) > 5:
                chinese_name = "沪银" if prefix == "AG" else "沪金"
                contract = "%s2702" % chinese_name
                fallback_p = 12625.0 if prefix == "AG" else 885.56
                latest = float(parts[3]) if parts[3].replace('.','',1).isdigit() else fallback_p
                pre_close = float(parts[4]) if parts[4].replace('.','',1).isdigit() else latest
                change = latest - pre_close
                change_pct = (change / pre_close * 100) if pre_close > 0 else 0.0
                volume = parts[6] if len(parts) > 6 else "1000"
                open_interest = parts[13] if len(parts) > 13 else "50000"
                price_fmt = "%.2f" if prefix == "AU" else "%.0f"
                
                return {
                    "contract": contract,
                    "price": price_fmt % latest,
                    "change": (price_fmt % change if prefix == "AU" else "%.0f" % change),
                    "change_pct": "%+.2f%%" % change_pct,
                    "volume": str(volume),
                    "open_interest": str(open_interest),
                    "bid1_p": price_fmt % (latest-1.0),
                    "bid1_v": "1",
                    "ask1_p": price_fmt % (latest+1.0),
                    "ask1_v": "1"
                }
        raise ValueError("Tencent quote fetch failed")


class AkShareQuoteSource(BaseQuoteSource):
    def get_quote(self, target_type: str) -> dict:
        import akshare as ak
        prefix = "AG" if target_type == "沪银" else "AU"
        contract_code = "ag2702" if target_type == "沪银" else "au2702"
        df = ak.futures_zh_spot(symbol=contract_code)
        if df is not None and not df.empty:
            row = df.iloc[0]
            fallback_p = 12625.0 if prefix == "AG" else 885.56
            latest = float(row.get('settle', row.get('price', fallback_p)))
            pre_settle = float(row.get('pre_settle', latest))
            change = latest - pre_settle
            change_pct = (change / pre_settle * 100) if pre_settle > 0 else 0.0
            chinese_name = "沪银" if prefix == "AG" else "沪金"
            price_fmt = "%.2f" if prefix == "AU" else "%.0f"
            return {
                "contract": "%s2702" % chinese_name,
                "price": price_fmt % latest,
                "change": price_fmt % change,
                "change_pct": "%+.2f%%" % change_pct,
                "volume": str(row.get('volume', 10000)),
                "open_interest": str(row.get('hold', 50000)),
                "bid1_p": price_fmt % (latest-1.0),
                "bid1_v": "1",
                "ask1_p": price_fmt % (latest+1.0),
                "ask1_v": "1"
            }
        raise ValueError("AkShare quote fetch failed")


class EastMoneyQuoteSource(BaseQuoteSource):
    def get_quote(self, target_type: str) -> dict:
        prefix = "AG" if target_type == "沪银" else "AU"
        em_secid = "114.AG2702" if target_type == "沪银" else "114.AU2702"
        url = "https://push2.eastmoney.com/api/qt/stock/get?secid=%s&fields=f43,f57,f58,f169,f170,f46,f44,f51,f52,f50,f47,f60,f48,f168,f161,f162,f163" % em_secid
        headers = {"Referer": "https://quote.eastmoney.com", "User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200:
            data = resp.json().get("data")
            if data:
                fallback_p = 12625.0 if prefix == "AG" else 885.56
                latest = float(data.get('f43', fallback_p * 100) / 100.0)
                pre_close = float(data.get('f60', latest))
                change = latest - pre_close
                change_pct = float(data.get('f170', 0.0)) / 100.0
                chinese_name = "沪银" if prefix == "AG" else "沪金"
                price_fmt = "%.2f" if prefix == "AU" else "%.0f"
                return {
                    "contract": "%s2702" % chinese_name,
                    "price": price_fmt % latest,
                    "change": price_fmt % change,
                    "change_pct": "%+.2f%%" % change_pct,
                    "volume": str(data.get('f47', 10000)),
                    "open_interest": str(data.get('f48', 50000)),
                    "bid1_p": price_fmt % (latest-1.0),
                    "bid1_v": "1",
                    "ask1_p": price_fmt % (latest+1.0),
                    "ask1_v": "1"
                }
        raise ValueError("EastMoney quote fetch failed")


QUOTE_SOURCES = {
    "新浪财经 (Sina)": SinaQuoteSource(),
    "腾讯财经 (Tencent)": TencentQuoteSource(),
    "Tushare 数据": AkShareQuoteSource(),
    "AkShare": AkShareQuoteSource(),
    "东方财富 (EastMoney)": EastMoneyQuoteSource(),
}


class CommodityQuoteWorker(QObject):
    data_fetched = pyqtSignal(str, dict)
    finished = pyqtSignal()

    def __init__(self, target_type="沪银", data_source="新浪财经 (Sina)"):
        super().__init__()
        self.target_type = target_type
        self.data_source = data_source
        self.running = True

    def set_target(self, target_type):
        self.target_type = target_type

    def set_data_source(self, data_source):
        self.data_source = data_source

    def stop(self):
        self.running = False

    @pyqtSlot()
    def do_work(self):
        import time
        retry_count = 0
        while self.running:
            market_open = check_is_market_open(market_type=self.target_type)
            if not market_open:
                for _ in range(300):
                    if not self.running:
                        break
                    time.sleep(0.1)
                continue
            
            try:
                source = QUOTE_SOURCES.get(self.data_source, SinaQuoteSource())
                info = source.get_quote(self.target_type)
                
                if info:
                    self.data_fetched.emit(self.target_type, info)
                    retry_count = 0
                else:
                    retry_count += 1
            except Exception as e:
                log_error(e, "QuoteWorker [%s - %s]" % (self.target_type, self.data_source))
                retry_count += 1
            
            sleep_sec = 2.0
            if retry_count > 3:
                sleep_sec = min(30.0, 2.0 * (2 ** (retry_count - 3)))
            
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
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)

        self.comm_combo = QComboBox()
        self.comm_combo.addItems(["沪银 (AG) - 15千克/手", "沪金 (AU) - 1000克/手"])
        self.comm_combo.setStyleSheet("""
            QComboBox {
                background-color: #262b36; color: #38bdf8; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 12px;
            }
            QComboBox QAbstractItemView { background-color: #1e222b; color: white; selection-background-color: #0284c7; }
        """)

        saved_comm_idx = 0
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            saved_comm_idx = self.parent_window.saved_calc_params.get("comm_idx", 0)
        self.comm_combo.setCurrentIndex(saved_comm_idx)
        self.comm_combo.currentIndexChanged.connect(self.on_commodity_combo_changed)

        lbl0 = QLabel("计算品种:")
        lbl0.setStyleSheet("color: #e2e8f0; font-size: 12px; font-weight: bold;")
        form.addRow(lbl0, self.comm_combo)

        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["做多 (Buy Long)", "做空 (Sell Short)"])
        self.dir_combo.setStyleSheet("""
            QComboBox {
                background-color: #262b36; color: #38bdf8; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 12px;
            }
            QComboBox QAbstractItemView { background-color: #1e222b; color: white; selection-background-color: #0284c7; }
        """)
        
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            p_data = self.parent_window.saved_calc_params
            self.dir_combo.setCurrentIndex(p_data.get("dir_idx", 1))

        self.dir_combo.currentIndexChanged.connect(self.on_param_changed)

        lbl1 = QLabel("多空头寸:")
        lbl1.setStyleSheet("color: #e2e8f0; font-size: 12px; font-weight: bold;")
        form.addRow(lbl1, self.dir_combo)

        default_p = 12625.0 if saved_comm_idx == 0 else 885.56
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            saved_p = self.parent_window.saved_calc_params.get("open_price", None)
            if saved_p is not None:
                default_p = saved_p

        self.open_price_spin = QDoubleSpinBox()
        self.open_price_spin.setRange(0.1, 999999.0)
        self.open_price_spin.setDecimals(2)
        self.open_price_spin.setValue(default_p)
        self.open_price_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #262b36; color: #ffffff; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 12px;
            }
        """)
        self.open_price_spin.valueChanged.connect(self.on_param_changed)

        lbl2 = QLabel("开仓价格:")
        lbl2.setStyleSheet("color: #e2e8f0; font-size: 12px; font-weight: bold;")
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
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 12px;
            }
        """)
        self.lots_spin.valueChanged.connect(self.on_param_changed)

        lbl3 = QLabel("持仓手数:")
        lbl3.setStyleSheet("color: #e2e8f0; font-size: 12px; font-weight: bold;")
        form.addRow(lbl3, self.lots_spin)

        saved_comm = 0.0020
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            saved_comm = self.parent_window.saved_calc_params.get("comm_rate", 0.0020)

        self.comm_spin = QDoubleSpinBox()
        self.comm_spin.setRange(0.0, 1.0)
        self.comm_spin.setDecimals(4)
        self.comm_spin.setSingleStep(0.001)
        self.comm_spin.setValue(saved_comm)
        self.comm_spin.setSuffix("%")
        self.comm_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #262b36; color: #38bdf8; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 12px;
            }
        """)
        self.comm_spin.valueChanged.connect(self.on_param_changed)

        lbl4 = QLabel("单边佣金费率:")
        lbl4.setStyleSheet("color: #e2e8f0; font-size: 12px; font-weight: bold;")
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

        self.comm_fee_lbl = QLabel("来回佣金: 0.0 元 (费率: 0.04%)")
        self.comm_fee_lbl.setStyleSheet("color: #facc15; font-size: 11px; border: none;")
        self.comm_fee_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.comm_fee_lbl)

        self.info_lbl = QLabel("当前现价: -- | 合约乘数: 15千克/手")
        self.info_lbl.setStyleSheet("color: #64748b; font-size: 10px; border: none;")
        self.info_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.info_lbl)

        layout.addWidget(self.result_card)

        save_close_btn = QPushButton("保存并关闭窗口")
        save_close_btn.setStyleSheet("background-color: #0284c7; color: white; border-radius: 5px; padding: 7px; font-weight: bold;")
        save_close_btn.clicked.connect(self.on_save_and_close)
        layout.addWidget(save_close_btn)

        self.calculate()

    def on_commodity_combo_changed(self, idx):
        if idx == 0:
            self.open_price_spin.setValue(12625.0)
        else:
            self.open_price_spin.setValue(885.56)
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

            curr_p = self.open_price_spin.value()
            if self.parent_window:
                try:
                    if comm_type == "沪银" and hasattr(self.parent_window, 'silver_data'):
                        curr_p = float(self.parent_window.silver_data.get('price', curr_p))
                    elif comm_type == "沪金" and hasattr(self.parent_window, 'gold_data'):
                        curr_p = float(self.parent_window.gold_data.get('price', curr_p))
                except Exception:
                    pass

            open_p = self.open_price_spin.value()
            lots = self.lots_spin.value()
            is_long = (self.dir_combo.currentIndex() == 0)

            diff = (curr_p - open_p) if is_long else (open_p - curr_p)
            gross_pnl = diff * mult * lots

            single_rate = self.comm_spin.value() / 100.0
            round_rate = single_rate * 2.0

            turnover = (open_p + curr_p) * mult * lots
            total_commission = turnover * single_rate

            net_pnl = gross_pnl - total_commission

            self.info_lbl.setText("当前%s参考价: %.2f  |  乘数: %d%s" % (comm_type, curr_p, int(mult), mult_unit))
            self.comm_fee_lbl.setText("来回佣金扣除: -%.1f 元 (双边费率: %.3f%%)" % (total_commission, round_rate*100))

            if net_pnl >= 0:
                self.pnl_val_lbl.setText("净浮盈: +%,.1f 元" % net_pnl)
                self.pnl_val_lbl.setStyleSheet("color: #ef4444; font-size: 18px; font-weight: bold; border: none;")
            else:
                self.pnl_val_lbl.setText("净浮亏: %,.1f 元" % net_pnl)
                self.pnl_val_lbl.setStyleSheet("color: #22c55e; font-size: 18px; font-weight: bold; border: none;")
        except Exception:
            pass

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
        settings_file = os.path.join(CACHE_DIR, "config.json")
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
            self.lock_btn.setToolTip("窗口已锁定（无法拖动）")
        else:
            self.lock_btn.setText("[开]")
            self.lock_btn.setToolTip("窗口已解锁（可拖动）")

        self.water_enabled = data.get("water_enabled", True)
        self.water_interval_min = data.get("water_interval_min", 45)
        self.sport_enabled = data.get("sport_enabled", True)
        self.sport_interval_min = data.get("sport_interval_min", 90)

        x = data.get("pos_x", -1)
        y = data.get("pos_y", -1)
        if x != -1 and y != -1:
            self.move(x, y)

        calc_dir = data.get("calc_dir_idx", 1)
        calc_price = data.get("calc_open_price", 12625.0)
        calc_lots = data.get("calc_lots", 1)
        calc_comm = data.get("calc_comm_rate", 0.0020)
        self.saved_calc_params = {
            "dir_idx": calc_dir,
            "open_price": calc_price,
            "lots": calc_lots,
            "comm_rate": calc_comm
        }
        self.update_compact_pnl()

    def save_settings(self):
        settings_file = os.path.join(CACHE_DIR, "config.json")
        theme_idx = 0
        if hasattr(self, 'settings_btn') and hasattr(self, 'current_bg_color'):
            theme_names = list(COLOR_THEMES.keys())
            for idx, name in enumerate(theme_names):
                if COLOR_THEMES[name]["bg_color"] == self.current_bg_color:
                    theme_idx = idx
                    break

        data = {
            "theme_index": theme_idx,
            "opacity": self.windowOpacity(),
            "ontop": bool(self.windowFlags() & Qt.WindowStaysOnTopHint),
            "locked": self.is_locked,
            "water_enabled": self.water_enabled,
            "water_interval_min": self.water_interval_min,
            "sport_enabled": self.sport_enabled,
            "sport_interval_min": self.sport_interval_min,
            "pos_x": self.x(),
            "pos_y": self.y(),
            "calc_dir_idx": self.saved_calc_params.get("dir_idx", 1),
            "calc_open_price": self.saved_calc_params.get("open_price", 12625.0),
            "calc_lots": self.saved_calc_params.get("lots", 1),
            "calc_comm_rate": self.saved_calc_params.get("comm_rate", 0.0020)
        }

        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as sf:
                    old_cfg = json.load(sf)
                    if "server_chan_key" in old_cfg:
                        data["server_chan_key"] = old_cfg["server_chan_key"]
                    if "server_key" in old_cfg:
                        data["server_key"] = old_cfg["server_key"]
            except Exception:
                pass

        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
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

        self.water_enabled = True
        self.water_interval_min = 45
        self.sport_enabled = True
        self.sport_interval_min = 90

        self.saved_calc_params = {"dir_idx": 1, "open_price": 12625.0, "lots": 1, "comm_rate": 0.0020}
        
        self.ag_contract = "沪银2702"
        self.au_contract = "沪金2702"

        self.silver_data = {
            "contract": "沪银2702",
            "price": "12625",
            "change": "+50",
            "change_pct": "+0.40%",
            "volume": "366524",
            "open_interest": "242022",
            "bid1_p": "12624",
            "bid1_v": "1",
            "ask1_p": "12626",
            "ask1_v": "1"
        }

        self.gold_data = {
            "contract": "沪金2702",
            "price": "885.56",
            "change": "+5.28",
            "change_pct": "+0.60%",
            "volume": "45210",
            "open_interest": "128400",
            "bid1_p": "885.50",
            "bid1_v": "1",
            "ask1_p": "885.60",
            "ask1_v": "1"
        }

        self.init_ui()
        self.load_settings()
        self.init_tray()
        self.init_workers()
        self.init_health_timers()
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
        self.lock_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; font-size: 12px; font-weight: bold; color: #38bdf8; }
            QPushButton:hover { background-color: rgba(255,255,255,0.1); border-radius: 4px; }
        """)
        self.lock_btn.setToolTip("点击锁定/解锁窗口位置")
        self.lock_btn.clicked.connect(self.toggle_lock)

        self.dock_btn = QPushButton("◀")
        self.dock_btn.setFixedSize(28, 28)
        self.dock_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; font-size: 13px; color: #38bdf8; font-weight: bold; }
            QPushButton:hover { background-color: rgba(255,255,255,0.1); border-radius: 4px; }
        """)
        self.dock_btn.setToolTip("点击缩进到桌面右侧，鼠标移上去自动展开")
        self.dock_btn.clicked.connect(self.toggle_dock)

        self.calc_btn = QPushButton("🧮")
        self.calc_btn.setFixedSize(28, 28)
        self.calc_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; font-size: 14px; color: #22c55e; }
            QPushButton:hover { background-color: rgba(255,255,255,0.1); border-radius: 4px; }
        """)
        self.calc_btn.setToolTip("实时持仓盈亏计算器")
        self.calc_btn.clicked.connect(self.open_calculator)

        self.alert_btn = QPushButton("🔔")
        self.alert_btn.setFixedSize(28, 28)
        self.alert_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; font-size: 14px; color: #38bdf8; }
            QPushButton:hover { background-color: rgba(255,255,255,0.1); border-radius: 4px; }
        """)
        self.alert_btn.setToolTip("价格预警管理")
        self.alert_btn.clicked.connect(self.open_price_alert)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; font-size: 14px; color: #a1a1aa; }
            QPushButton:hover { color: #ffffff; background-color: rgba(255,255,255,0.1); border-radius: 4px; }
        """)
        self.settings_btn.setToolTip("打开高级设置与皮肤切换")
        self.settings_btn.clicked.connect(self.open_settings)

        top_bar.addWidget(self.lock_btn)
        top_bar.addWidget(self.dock_btn)
        top_bar.addWidget(self.calc_btn)
        top_bar.addWidget(self.alert_btn)
        top_bar.addWidget(self.settings_btn)
        top_bar.addStretch()

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; font-size: 14px; color: #a1a1aa; }
            QPushButton:hover { color: #ffffff; background-color: rgba(255,255,255,0.1); border-radius: 4px; }
        """)
        self.close_btn.setToolTip("点击隐藏到系统托盘区")
        self.close_btn.clicked.connect(self.hide)
        top_bar.addWidget(self.close_btn)
        c_layout.addLayout(top_bar)

        self.datetime_label = QLabel()
        self.datetime_label.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.datetime_label)

        self.status_card = QWidget()
        self.status_card.setStyleSheet(f"""
            QWidget {{
                background-color: {self.current_card_bg}; border-radius: 8px; border: 1px solid rgba(255,255,255,0.06);
            }}
        """)
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setSpacing(4)

        top_row = QHBoxLayout()
        self.stock_status_label = QLabel("股市：已收盘")
        self.stock_status_label.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        
        self.cal_btn = QPushButton("休市日历")
        self.cal_btn.setStyleSheet("""
            QPushButton {
                background-color: #262b36; color: #f87171; border: 1px solid rgba(248, 113, 113, 0.3); border-radius: 4px; padding: 3px 6px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #333b4d; }
        """)
        self.cal_btn.clicked.connect(self.show_calendar)
        
        top_row.addWidget(self.stock_status_label)
        top_row.addStretch()
        top_row.addWidget(self.cal_btn)
        status_layout.addLayout(top_row)

        sep_line = QLabel()
        sep_line.setFixedHeight(1)
        sep_line.setStyleSheet("background-color: rgba(255,255,255,0.08); border: none;")
        status_layout.addWidget(sep_line)

        self.silver_status_label = QLabel("白银期货：交易中 (Live)")
        self.silver_status_label.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        status_layout.addWidget(self.silver_status_label)

        c_layout.addWidget(self.status_card)

        self.silver_board = QLabel()
        self.silver_board.setAlignment(Qt.AlignCenter)
        self.update_silver_board_ui()
        c_layout.addWidget(self.silver_board)

        self.compact_pnl_card = QWidget()
        self.compact_pnl_card.setStyleSheet("""
            QWidget {
                background-color: #141820; border-radius: 8px; border: 1px solid rgba(56, 189, 248, 0.3);
            }
        """)
        compact_layout = QVBoxLayout(self.compact_pnl_card)
        compact_layout.setContentsMargins(10, 8, 10, 8)
        compact_layout.setSpacing(4)

        self.compact_pnl_val_lbl = QLabel("净浮盈: +0.0 元")
        self.compact_pnl_val_lbl.setStyleSheet("color: #ef4444; font-size: 16px; font-weight: bold; border: none; background: transparent;")
        self.compact_pnl_val_lbl.setAlignment(Qt.AlignCenter)
        compact_layout.addWidget(self.compact_pnl_val_lbl)

        self.compact_open_lbl = QLabel("多/空开仓价: -- (1手)")
        self.compact_open_lbl.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        self.compact_open_lbl.setAlignment(Qt.AlignCenter)
        compact_layout.addWidget(self.compact_open_lbl)

        self.compact_comm_lbl = QLabel("来回佣金扣除: 0.0 元 (双边费率: 0.040%)")
        self.compact_comm_lbl.setStyleSheet("color: #facc15; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        self.compact_comm_lbl.setAlignment(Qt.AlignCenter)
        compact_layout.addWidget(self.compact_comm_lbl)

        c_layout.addWidget(self.compact_pnl_card)

        self.next_holiday_label = QLabel("距离下一节假日：元旦 (56天)")
        self.next_holiday_label.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.next_holiday_label)

        self.macro_board = QLabel()
        self.macro_board.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.macro_board)

        self.apply_theme(self.current_bg_color, self.current_time_color, self.current_card_bg, self.current_accent)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)
        self.update_clock()

        self.resize(340, 620)

    def init_workers(self):
        self.ag_thread = QThread()
        self.ag_worker = CommodityQuoteWorker("沪银", "新浪财经 (Sina)")
        self.ag_worker.moveToThread(self.ag_thread)
        self.ag_thread.started.connect(self.ag_worker.do_work)
        self.ag_worker.data_fetched.connect(self.on_quote_data_updated)
        self.ag_thread.start()

        self.au_thread = QThread()
        self.au_worker = CommodityQuoteWorker("沪金", "新浪财经 (Sina)")
        self.au_worker.moveToThread(self.au_thread)
        self.au_thread.started.connect(self.au_worker.do_work)
        self.au_worker.data_fetched.connect(self.on_quote_data_updated)
        self.au_thread.start()

    def init_health_timers(self):
        self.water_timer = QTimer(self)
        self.water_timer.timeout.connect(self.show_water_reminder)
        
        self.sport_timer = QTimer(self)
        self.sport_timer.timeout.connect(self.show_sport_reminder)
        
        self.update_health_timers()

    def update_health_timers(self):
        if self.water_enabled:
            self.water_timer.setInterval(self.water_interval_min * 60 * 1000)
            if not self.water_timer.isActive():
                self.water_timer.start()
        else:
            self.water_timer.stop()

        if self.sport_enabled:
            self.sport_timer.setInterval(self.sport_interval_min * 60 * 1000)
            if not self.sport_timer.isActive():
                self.sport_timer.start()
        else:
            self.sport_timer.stop()

    def show_water_reminder(self):
        try:
            for _ in range(2):
                winsound.Beep(880, 150)
                import time
                time.sleep(0.08)
        except Exception:
            pass
        msg = "已连续专注 %d 分钟啦！\n记得及时补充温水，保持身体活力哦~" % self.water_interval_min
        dlg = SilentTipDialog("健康饮水提醒", msg, self)
        dlg.exec_()

    def show_sport_reminder(self):
        try:
            for _ in range(3):
                winsound.Beep(1200, 200)
                import time
                time.sleep(0.1)
        except Exception:
            pass
        msg = "已久坐满 %d 分钟啦！\n站起来活动一下筋骨、伸个懒腰，眺望远方休息一下吧！" % self.sport_interval_min
        dlg = SilentTipDialog("久坐运动提醒", msg, self)
        dlg.exec_()

    def on_source_changed(self, index):
        sources = ["新浪财经 (Sina)", "腾讯财经 (Tencent)", "Tushare 数据", "AkShare", "东方财富 (EastMoney)"]
        selected_source = sources[index] if 0 <= index < len(sources) else "新浪财经 (Sina)"
        if hasattr(self, 'ag_worker'):
            self.ag_worker.set_data_source(selected_source)
        if hasattr(self, 'au_worker'):
            self.au_worker.set_data_source(selected_source)
        
    def update_compact_pnl(self):
        try:
            comm_type = "沪银"
            curr_p = 12625.0
            if hasattr(self, 'silver_data') and self.silver_data:
                try:
                    curr_p = float(self.silver_data.get('price', 12625.0))
                except Exception:
                    pass
            
            mult = 15.0

            p_data = getattr(self, 'saved_calc_params', {"dir_idx": 1, "open_price": curr_p, "lots": 1, "comm_rate": 0.0020})
            open_p = p_data.get("open_price", curr_p)
            lots = p_data.get("lots", 1)
            dir_idx = p_data.get("dir_idx", 1)
            is_long = (dir_idx == 0)

            if hasattr(self, 'compact_open_lbl'):
                dir_str = "多头" if is_long else "空头"
                self.compact_open_lbl.setText("%s开仓价: %.2f  (%d手)" % (dir_str, open_p, lots))

            diff = (curr_p - open_p) if is_long else (open_p - curr_p)
            gross_pnl = diff * mult * lots

            single_rate = p_data.get("comm_rate", 0.0020) / 100.0
            round_rate = single_rate * 2.0

            turnover = (open_p + curr_p) * mult * lots
            total_commission = turnover * single_rate

            net_pnl = gross_pnl - total_commission

            if hasattr(self, 'compact_comm_lbl'):
                self.compact_comm_lbl.setText("来回佣金扣除: -%.1f 元 (双边费率: %.3f%%)" % (total_commission, round_rate*100))

            if hasattr(self, 'compact_pnl_val_lbl'):
                if net_pnl >= 0:
                    self.compact_pnl_val_lbl.setText("净浮盈: +%,.1f 元" % net_pnl)
                    self.compact_pnl_val_lbl.setStyleSheet("color: #ef4444; font-size: 15px; font-weight: bold; border: none; background: transparent;")
                else:
                    self.compact_pnl_val_lbl.setText("净浮亏: %,.1f 元" % net_pnl)
                    self.compact_pnl_val_lbl.setStyleSheet("color: #22c55e; font-size: 15px; font-weight: bold; border: none; background: transparent;")
        except Exception as e:
            log_error(e, "UpdateCompactPnL")

    def on_quote_data_updated(self, target_type, info):
        if not self.is_market_open(datetime.datetime.now()):
            return
            
        contract = info.get("contract", "")
        if target_type == "沪银":
            self.silver_data.update(info)
            if contract and len(contract) >= 2:
                self.ag_contract = contract
        else:
            self.gold_data.update(info)
            if contract and len(contract) >= 2:
                self.au_contract = contract

        self.update_silver_board_ui()
        self.update_compact_pnl()
        
        if hasattr(self, 'calc_dlg') and self.calc_dlg and self.calc_dlg.isVisible():
            self.calc_dlg.calculate()

        self.check_price_alerts(info)

    def check_price_alerts(self, info):
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
                            cond_desc = "价格涨至 %.2f" % target if cond_type == "up" else "价格跌至 %.2f" % target
                            msg = "价格已到预警线！合约 %s\n当前最新价: %.2f\n条件: %s" % (current_contract, current_price, cond_desc)
                            
                            try:
                                import time
                                for _ in range(3):
                                    winsound.Beep(1200, 350)
                                    time.sleep(0.15)
                            except Exception:
                                pass

                            dlg = SilentTipDialog("价格预警触发", msg, self)
                            dlg.exec_()
            
            if updated:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(alerts, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def update_silver_board_ui(self):
        d_ag = self.silver_data
        d_au = self.gold_data
        try:
            chg_ag = float(d_ag.get('change', 0))
        except Exception:
            chg_ag = 0.0

        try:
            chg_au = float(d_au.get('change', 0))
        except Exception:
            chg_au = 0.0

        color_ag = "#ef4444" if chg_ag >= 0 else "#22c55e"
        arrow_ag = "+" if chg_ag >= 0 else ""

        color_au = "#ef4444" if chg_au >= 0 else "#22c55e"
        arrow_au = "+" if chg_au >= 0 else ""

        html_text = (
            f'<table width="100%" cellspacing="0" cellpadding="0" style="font-family: Consolas, monospace; background-color: #141820; border-radius: 8px; padding: 6px;">'
            f'<tr>'
            f'<td style="font-size: 11px; font-weight: bold; color: #94a3b8; padding: 3px 6px;">{self.ag_contract}</td>'
            f'<td align="center" style="font-size: 14px; font-weight: bold; color: #ffffff; padding: 3px 6px;">{d_ag.get("price", "12625")}</td>'
            f'<td align="right" style="font-size: 11px; font-weight: bold; color: {color_ag}; padding: 3px 6px;">{arrow_ag}{d_ag.get("change_pct", "+0.40%")}</td>'
            f'</tr>'
            f'<tr>'
            f'<td style="font-size: 11px; font-weight: bold; color: #94a3b8; padding: 3px 6px; border-top: 1px solid rgba(255,255,255,0.06);">{self.au_contract}</td>'
            f'<td align="center" style="font-size: 14px; font-weight: bold; color: #ffffff; padding: 3px 6px; border-top: 1px solid rgba(255,255,255,0.06);">{d_au.get("price", "885.56")}</td>'
            f'<td align="right" style="font-size: 11px; font-weight: bold; color: {color_au}; padding: 3px 6px; border-top: 1px solid rgba(255,255,255,0.06);">{arrow_au}{d_au.get("change_pct", "+0.60%")}</td>'
            f'</tr>'
            f'</table>'
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
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger or reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.raise_()
                self.activateWindow()

    def closeEvent(self, event: QCloseEvent):
        if self.is_forced_exit:
            self.save_settings()
            event.accept()
        else:
            event.ignore()
            self.hide()
            if hasattr(self, 'tray_icon'):
                self.tray_icon.showMessage(
                    "桌面市场时钟",
                    "程序已最小化到系统托盘区。点击右下角向上箭头可随时呼出，如需彻底退出请右键点击托盘图标选择“退出程序”。",
                    QSystemTrayIcon.Information,
                    3000
                )

    def real_quit(self):
        self.is_forced_exit = True
        self.save_settings()
        
        if hasattr(self, 'ag_worker'):
            self.ag_worker.stop()
        if hasattr(self, 'au_worker'):
            self.au_worker.stop()

        if hasattr(self, 'ag_thread'):
            self.ag_thread.quit()
            self.ag_thread.wait(1000)
        if hasattr(self, 'au_thread'):
            self.au_thread.quit()
            self.au_thread.wait(1000)

        self.tray_icon.hide()
        QApplication.quit()

    def apply_theme(self, bg_color, time_color, card_bg, accent):
        self.current_bg_color = bg_color
        self.current_time_color = time_color
        self.current_card_bg = card_bg
        self.current_accent = accent

        self.container.setStyleSheet("""
            QWidget#MainContainer {
                background-color: %s;
                border-radius: 12px;
                border: none;
            }
        """ % bg_color)

        self.current_time_color = time_color
        self.update_clock()

        self.silver_board.setStyleSheet("""
            QLabel {
                background-color: %s; border-radius: 8px; padding: 4px; border: 1px solid rgba(255,255,255,0.06);
            }
        """ % card_bg)

        self.status_card.setStyleSheet("""
            QWidget {
                background-color: %s; border-radius: 8px; border: 1px solid rgba(255,255,255,0.06);
            }
        """ % card_bg)

        self.next_holiday_label.setStyleSheet("""
            QLabel {
                background-color: %s; color: #38bdf8; font-size: 12px; font-weight: bold; border-radius: 8px; padding: 5px; border: 1px solid rgba(56, 189, 248, 0.2);
            }
        """ % card_bg)

    def toggle_dock(self):
        screen = self.screen().availableGeometry() if hasattr(self, 'screen') else QApplication.desktop().screenGeometry(self)
        screen_w = screen.width()
        if not self.is_docked:
            self.normal_geometry = self.geometry()
            docked_w = 38
            self.setGeometry(screen_w - docked_w, self.y(), docked_w, self.height())
            self.is_docked = True
            self.dock_btn.setText("▶")
            self.dock_btn.setToolTip("已缩进到右侧，鼠标悬停自动展开")
        else:
            if not self.normal_geometry.isNull():
                self.setGeometry(self.normal_geometry)
            else:
                self.resize(340, 620)
            self.is_docked = False
            self.dock_btn.setText("◀")
            self.dock_btn.setToolTip("点击缩进到桌面右侧")
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
            self.lock_btn.setToolTip("窗口已锁定（无法拖动）")
        else:
            self.lock_btn.setText("[开]")
            self.lock_btn.setToolTip("窗口已解锁（可拖动）")
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

    def is_market_open(self, now):
        return check_is_market_open(now)

    def update_clock(self):
        now = datetime.datetime.now()
        week_days = ['星期一','星期二','星期三','星期四','星期五','星期六','星期日']
        
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%Y年%m月%d日") + " " + week_days[now.weekday()]
        self.datetime_label.setText(f'<div align="center"><span style="font-size: 32px; font-weight: bold; font-family: Consolas, monospace; color: {self.current_time_color};">{time_str}</span><br><span style="font-size: 13px; color: #94a3b8; font-family: sans-serif;">{date_str}</span></div>')

        self.update_next_holiday(now)
        self.update_macro_countdown(now)

        date_key = now.strftime("%Y-%m-%d")
        holiday_info = HOLIDAY_SCHEDULE.get(date_key, None)

        if holiday_info:
            types = holiday_info.get("types", []) if isinstance(holiday_info, dict) else holiday_info
            reason = holiday_info.get("reason", "休市") if isinstance(holiday_info, dict) else "休市"
            
            if "A" in types:
                self.stock_status_label.setText("股市：%s" % reason)
            else:
                self.update_stock_countdown(now)

            if "AG" in types or "AU" in types:
                self.silver_status_label.setText("贵金属：%s" % reason)
            else:
                self.update_silver_countdown(now)
        elif now.weekday() >= 5:
            self.stock_status_label.setText("股市：周末休市")
            self.silver_status_label.setText("贵金属：周末休市 (非交易日)")
        else:
            self.update_stock_countdown(now)
            self.update_silver_countdown(now)

    def update_stock_countdown(self, now):
        current_time = now.time()
        
        t_m_open = datetime.time(9, 30, 0)
        t_m_close = datetime.time(11, 30, 0)
        t_a_open = datetime.time(13, 0, 0)
        t_a_close = datetime.time(15, 0, 0)

        is_trading = False
        closing_dt = None

        if t_m_open <= current_time <= t_m_close:
            is_trading = True
            closing_dt = datetime.datetime.combine(now.date(), t_m_close)
        elif t_a_open <= current_time <= t_a_close:
            is_trading = True
            closing_dt = datetime.datetime.combine(now.date(), t_a_close)

        if is_trading and closing_dt:
            diff = closing_dt - now
            if diff.total_seconds() > 0:
                hours = int(diff.total_seconds() // 3600)
                minutes = int((diff.total_seconds() % 3600) // 60)
                seconds = int(diff.total_seconds() % 60)
                if hours > 0:
                    time_str = "%02d小时%02d分%02d秒" % (hours, minutes, seconds)
                else:
                    time_str = "%02d分%02d秒" % (minutes, seconds)
                self.stock_status_label.setText("股市：交易中 (距闭市 %s)" % time_str)
            else:
                self.stock_status_label.setText("股市：即将闭市...")
        else:
            if current_time < t_m_open:
                next_open = datetime.datetime.combine(now.date(), t_m_open)
            elif t_m_close < current_time < t_a_open:
                next_open = datetime.datetime.combine(now.date(), t_a_open)
            else:
                next_open = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), t_m_open)
                while next_open.weekday() >= 5:
                    next_open += datetime.timedelta(days=1)

            diff = next_open - now
            if diff.total_seconds() > 0:
                days = int(diff.total_seconds() // 86400)
                hours = int((diff.total_seconds() % 86400) // 3600)
                minutes = int((diff.total_seconds() % 3600) // 60)
                seconds = int(diff.total_seconds() % 60)
                if days > 0:
                    time_str = "%d天%02d时%02d分" % (days, hours, minutes)
                elif hours > 0:
                    time_str = "%02d时%02d分%02d秒" % (hours, minutes, seconds)
                else:
                    time_str = "%02d分%02d秒" % (minutes, seconds)
                self.stock_status_label.setText("股市：已收盘 (距开盘 %s)" % time_str)
            else:
                self.stock_status_label.setText("股市：即将开盘...")

    def update_silver_countdown(self, now):
        current_time = now.time()
        
        t_morning_open = datetime.time(9, 0, 0)
        t_morning_close = datetime.time(11, 30, 0)
        t_afternoon_open = datetime.time(13, 30, 0)
        t_afternoon_close = datetime.time(15, 0, 0)
        t_night_open = datetime.time(21, 0, 0)
        t_night_close = datetime.time(2, 30, 0)

        closing_dt = None
        is_trading = False

        if datetime.time(9, 0) <= current_time <= datetime.time(11, 30):
            is_trading = True
            closing_dt = datetime.datetime.combine(now.date(), t_morning_close)
        elif datetime.time(13, 30) <= current_time <= datetime.time(15, 0):
            is_trading = True
            closing_dt = datetime.datetime.combine(now.date(), t_afternoon_close)
        elif current_time >= datetime.time(21, 0) or current_time <= datetime.time(2, 30):
            is_trading = True
            if current_time <= datetime.time(2, 30):
                closing_dt = datetime.datetime.combine(now.date(), t_night_close)
            else:
                closing_dt = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), t_night_close)

        if is_trading and closing_dt:
            diff = closing_dt - now
            if diff.total_seconds() > 0:
                hours = int(diff.total_seconds() // 3600)
                minutes = int((diff.total_seconds() % 3600) // 60)
                seconds = int(diff.total_seconds() % 60)
                if hours > 0:
                    time_str = "%02d小时%02d分%02d秒" % (hours, minutes, seconds)
                else:
                    time_str = "%02d分%02d秒" % (minutes, seconds)
                self.silver_status_label.setText("贵金属：交易中 (距闭市 %s)" % time_str)
            else:
                self.silver_status_label.setText("贵金属：即将休市...")
        else:
            self.silver_status_label.setText("贵金属：已休市 (非交易时段)")

    def update_next_holiday(self, now):
        current_date = now.date()
        next_h_name = "元旦"
        next_h_days = 56
        
        future_holidays = []
        for d_str, info in HOLIDAY_SCHEDULE.items():
            h_date = datetime.datetime.strptime(d_str, "%Y-%m-%d").date()
            if h_date >= current_date:
                reason = info.get("reason", "节假日休市") if isinstance(info, dict) else "节假日休市"
                future_holidays.append((h_date, reason))
        
        future_holidays.sort(key=lambda x: x[0])
        if future_holidays:
            h_date, reason = future_holidays[0]
            delta = (h_date - current_date).days
            self.next_holiday_label.setText("距离下一节假日：%s (%d天后)" % (reason, delta))
        else:
            self.next_holiday_label.setText("近期暂无节假日安排")

    def update_macro_countdown(self, now):
        pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ClockWindow()
    window.show()
    sys.exit(app.exec_())
