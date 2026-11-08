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
from sync_alerts import sync_to_cloud

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".market_clock_cache")

def get_server_key():
    # 安全获取 Server酱 Key: 优先从环境变量读取，其次从 config.json 读取
    key = os.getenv("SERVER_CHAN_KEY")
    if key:
        return key.strip()
    try:
        config_file = os.path.join(CACHE_DIR, "config.json")
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("server_chan_key", "").strip()
    except Exception:
        pass
    return ""


# ===== 全局配置中心 (Configuration Center) =====
DEFAULT_AG_CONTRACT = "AG2702"
DEFAULT_AU_CONTRACT = "AU2702"
DEFAULT_AG_PRICE = 12523.0
DEFAULT_AU_PRICE = 874.6
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
            f.write(f"[{now_str}] ERROR in {context_msg}:\n")
            f.write(f"Type: {type(err).__name__} | Message: {str(err)}\n")
            f.write("Traceback:\n" + traceback.format_exc() + "\n")
            f.write("-" * 60 + "\n")
    except Exception:
        pass

# ===== 缓存自动清理机制（保留30天内数据） =====
def cleanup_cache():
    """清理缓存目录下超过30天的旧缓存文件，防止体积无限膨胀"""
    try:
        if not os.path.exists(CACHE_DIR):
            return
            
        now_ts = datetime.datetime.now().timestamp()
        expire_seconds = 30 * 24 * 3600  # 30天秒数
        
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
    
    # 周六凌晨 2:30 之前属于周五夜盘
    if weekday == 5 and t <= datetime.time(2, 30) and market_type == "AG":
        return True
    # 周六白天、周日全天休市
    if weekday >= 5:
        return False
        
    date_key = now.strftime("%Y-%m-%d")
    if date_key in HOLIDAY_SCHEDULE:
        info = HOLIDAY_SCHEDULE[date_key]
        market_hours = info.get("market_hours", {})
        
        # 针对具体品种包含精细化开市时间段的情况（如半日市）
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

    if market_type == "AG":
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

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "MarketDesktopClock"

def set_autostart(enable=True):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            app_path = os.path.abspath(sys.argv[0])
            if app_path.endswith(".py"):
                cmd = f'"{sys.executable}" "{app_path}"'
            else:
                cmd = f'"{app_path}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"设置开机自启失败: {e}")
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

        title_lbl = QLabel("🔔 " + title_text)
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
    def __init__(self, current_contract="AG2702", current_price=12500.0, parent=None):
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
        title = QLabel("🎯 设置合约价格预警")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8; margin-bottom: 6px;")
        layout.addWidget(title)

        form = QFormLayout()

        self.contract_combo = QComboBox()
        ag_c = getattr(self.parent_window, 'ag_contract', 'AG2702') if self.parent_window else "AG2702"
        au_c = getattr(self.parent_window, 'au_contract', 'AU2702') if self.parent_window else "AU2702"
        self.contract_combo.addItems([f"沪银 ({ag_c})", f"沪金 ({au_c})"])
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
        self.cond_combo.addItems(["合约价格涨到 (≥)", "合约价格跌到 (≤)"])
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
        self.price_spin.setDecimals(1)
        self.price_spin.setValue(self.current_price)
        self.price_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #262b36; color: #38bdf8; font-weight: bold;
                border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;
            }
        """)
        form.addRow("目标价格:", self.price_spin)

        layout.addLayout(form)

        self.hint_lbl = QLabel(f"💡 当前最新参考价: {self.current_price}")
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
            self.contract = getattr(self.parent_window, 'ag_contract', 'AG2702') if self.parent_window else "AG2702"
            p = 12500.0
            if self.parent_window and hasattr(self.parent_window, 'silver_data') and self.parent_window.current_commodity == "沪银":
                try:
                    p = float(self.parent_window.silver_data.get("price", 12500.0))
                except Exception:
                    pass
            self.price_spin.setValue(p)
            self.hint_lbl.setText(f"💡 当前最新参考价: {p}")
        else:
            self.contract = getattr(self.parent_window, 'au_contract', 'AU2702') if self.parent_window else "AU2702"
            p = 874.6
            if self.parent_window and hasattr(self.parent_window, 'silver_data') and self.parent_window.current_commodity == "沪金":
                try:
                    p = float(self.parent_window.silver_data.get("price", 874.6))
                except Exception:
                    pass
            self.price_spin.setValue(p)
            self.hint_lbl.setText(f"💡 当前最新参考价: {p}")

    def on_ok(self):
        idx = self.contract_combo.currentIndex()
        if idx == 0:
            self.contract = getattr(self.parent_window, 'ag_contract', 'AG2702') if self.parent_window else "AG2702"
        else:
            self.contract = getattr(self.parent_window, 'au_contract', 'AU2702') if self.parent_window else "AU2702"
            
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
        title = QLabel("🔔 涨跌目标位预警中心")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        top_row.addWidget(title)
        top_row.addStretch()

        add_btn = QPushButton("＋ 添加预警")
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

        sync_cloud_btn = QPushButton("☁️ 同步到云端")
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
                log_error(e, f"PriceAlert Load")
        
        self.table.setRowCount(len(alerts))
        for row, alert in enumerate(alerts):
            contract_item = QTableWidgetItem(alert.get("contract", ""))
            cond_str = "涨到 (≥)" if alert.get("type") == "up" else "跌到 (≤)"
            cond_item = QTableWidgetItem(cond_str)
            price_item = QTableWidgetItem(f"{alert.get('target', 0.0):.1f}")
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
        curr_contract = "AG2702"
        curr_price = 12500.0
        if self.parent_window and hasattr(self.parent_window, 'silver_data'):
            curr_contract = self.parent_window.silver_data.get("contract", "AG2702")
            try:
                curr_price = float(self.parent_window.silver_data.get("price", 12500.0))
            except Exception as e:
                log_error(e, f"PriceAlert Add")

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
                log_error(e, f"PriceAlert Delete")

    def sync_alerts_to_cloud(self):
        """一键将本地的 price_alerts.json 推送到 GitHub，并发送微信通知（已统一复用 sync_alerts.py）"""
        try:
            success, msg = sync_to_cloud()
            
            if success:
                dlg = SilentTipDialog(
                    "☁️ 云端同步与微信提醒成功", 
                    "最新的价格预警配置已成功处理，并已通过微信发送了同步通知！", 
                    self
                )
            else:
                dlg = SilentTipDialog("❌ 同步提示", f"同步过程提示：\n{msg}", self)
            dlg.exec_()
        except Exception as e:
            dlg = SilentTipDialog("❌ 同步失败", f"推送或发送微信通知失败：\n{e}", self)
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
        title_label = QLabel("📅 2026–2027 年股市及贵金属期货休市安排看板")
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

        legend_label = QLabel("🔴 A股休市  |  🟣 港股休市  |  🔵 贵金属期货休市")
        legend_label.setStyleSheet("color: #475569; font-size: 12px; font-weight: bold; margin-top: 6px;")
        layout.addWidget(legend_label)

        hint_label = QLabel("💡 点击带圆点的日期可查看具体休市原因")
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
            if "AG" in types: type_desc.append("贵金属期货")
            
            types_str = "、".join(type_desc)
            msg_text = f"休市市场：{types_str}\n具体说明：{reason}"
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
        title = QLabel("⚙ 桌面时钟设置与健康提醒")
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
        self.theme_combo.addItems(list(COLOR_THEMES.keys()) + ["🎨 自定义数字颜色..."])
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


class MiniTrendChartWidget(QWidget):
    period_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(145)
        self.setMouseTracking(True)
        self.current_price_str = "12523.0"
        self.change_str = "-1.38%"
        self.hovered_index = -1
        self.period_minutes = 5
        self.candles = []
        
        self.combo = QComboBox(self)
        self.combo.addItems(["5分钟", "15分钟", "30分钟", "60分钟", "120分钟", "日线", "周线", "月线"])
        self.combo.setGeometry(42, 2, 75, 20)
        self.combo.setStyleSheet("""
            QComboBox {
                background-color: #1a202c; color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 3px; padding: 1px 3px; font-size: 11px; font-weight: bold;
            }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 12px; border-left-width: 0px; }
            QComboBox QAbstractItemView { background-color: #0b0e14; color: #38bdf8; selection-background-color: #0284c7; selection-color: #ffffff; }
        """)
        self.combo.currentIndexChanged.connect(self.on_period_changed)
        self.load_candles_from_cache_or_default()

    def get_cache_filepath(self):
        parent_win = self.parent()
        while parent_win and not hasattr(parent_win, 'current_commodity'):
            parent_win = parent_win.parent()
        comm = getattr(parent_win, 'current_commodity', '沪银')
        os.makedirs(CACHE_DIR, exist_ok=True)
        return os.path.join(CACHE_DIR, f"candles_{comm}_{self.period_minutes}.json")

    def load_candles_from_cache_or_default(self):
        filepath = self.get_cache_filepath()
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        self.candles = self.clean_and_freeze_candles(data)
                        self.update()
                        return
            except Exception as e:
                log_error(e, f"Candles Load")
        self.generate_fallback_candles()

    def clean_and_freeze_candles(self, candles):
        if not check_is_market_open():
            cleaned = []
            for c in candles:
                cleaned.append(c)
            return cleaned
        return candles

    def save_candles_to_cache(self):
        try:
            filepath = self.get_cache_filepath()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.candles, f, ensure_ascii=False)
        except Exception:
            pass

    def on_period_changed(self, index):
        periods = [5, 15, 30, 60, 120, 1440, 10080, 43200]
        if 0 <= index < len(periods):
            self.period_minutes = periods[index]
            self.load_candles_from_cache_or_default()
            self.update()
            self.period_changed.emit(self.period_minutes)

    def generate_fallback_candles(self):
        base_p = float(self.current_price_str) if hasattr(self, 'current_price_str') and self.current_price_str.replace('.', '', 1).isdigit() else 12523.0
        self.candles = []
        delta_step = datetime.timedelta(minutes=self.period_minutes)
        
        anchor_time = datetime.datetime.now()
        if not check_is_market_open():
            if anchor_time.weekday() == 5:
                anchor_time = anchor_time.replace(hour=2, minute=30, second=0, microsecond=0)
            elif anchor_time.weekday() == 6:
                anchor_time = (anchor_time - datetime.timedelta(days=1)).replace(hour=2, minute=30, second=0, microsecond=0)
            elif anchor_time.hour < 9 and anchor_time.weekday() < 5:
                anchor_time = anchor_time.replace(hour=2, minute=30, second=0, microsecond=0)

        base_time = anchor_time - datetime.timedelta(minutes=28 * self.period_minutes)
        
        prices = [base_p]
        curr = base_p
        step_range = max(0.5, base_p * 0.0015)
        for _ in range(27):
            curr += random.uniform(-step_range, step_range)
            prices.insert(0, curr)
            
        for i in range(28):
            c_val = prices[i]
            prev_val = prices[i-1] if i > 0 else c_val
            o = prev_val
            h = max(o, c_val) + random.uniform(0, step_range * 0.6)
            l = min(o, c_val) - random.uniform(0, step_range * 0.6)
            vol = random.randint(100, 5000)
            
            if self.period_minutes >= 1440:
                weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                wd = weekdays[base_time.weekday()]
                t_str = base_time.strftime('%y-%m-%d') + " " + wd
            else:
                t_str = base_time.strftime("%y-%m-%d %H:%M")
            self.candles.append({"open": o, "high": h, "low": l, "close": c_val, "volume": vol, "time": t_str})
            base_time += delta_step
        self.update()

    def update_latest_price(self, price_val, change_pct_val=""):
        try:
            p = float(price_val)
            self.current_price_str = str(price_val)
            if change_pct_val:
                self.change_str = str(change_pct_val)
            
            if self.candles:
                curr = self.candles[-1]
                curr["close"] = p
                curr["high"] = max(curr["high"], p)
                curr["low"] = min(curr["low"], p)
            self.update()
        except Exception:
            pass

    def mouseMoveEvent(self, event):
        w = self.width()
        chart_w = w - 75
        n = len(self.candles)
        if n > 0 and chart_w > 0:
            x = event.x() - 12
            if 0 <= x <= chart_w:
                idx = int(x / (chart_w / n))
                if 0 <= idx < n:
                    if self.hovered_index != idx:
                        self.hovered_index = idx
                        self.update()
                        return
        if self.hovered_index != -1:
            self.hovered_index = -1
            self.update()

    def leaveEvent(self, event):
        if self.hovered_index != -1:
            self.hovered_index = -1
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        w = rect.width()
        h = rect.height()

        painter.setBrush(QBrush(QColor("#0b0e14")))
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 6, 6)

        painter.setPen(QPen(QColor(120, 20, 20, 100), 1, Qt.DotLine))
        for y_step in range(1, 5):
            y = int(24 + (h - 36) * y_step / 4)
            painter.drawLine(10, y, w - 70, y)
        for x_step in range(1, 6):
            x = int((w - 70) * x_step / 6)
            painter.drawLine(x, 24, x, h - 10)

        if not self.candles:
            return

        all_highs = [c["high"] for c in self.candles]
        all_lows = [c["low"] for c in self.candles]
        max_p = max(all_highs)
        min_p = min(all_lows)
        if max_p == min_p:
            max_p += 1.0
            min_p -= 1.0
        p_range = max_p - min_p

        all_vols = [c.get("volume", 100) for c in self.candles]
        max_vol = max(all_vols) if all_vols else 1000
        if max_vol <= 0:
            max_vol = 1000

        pad_top = 26
        pad_bot = 32
        draw_h = int((h - pad_top - pad_bot) * 0.72)
        vol_chart_h = (h - pad_top - pad_bot) - draw_h - 6
        vol_base_y = pad_top + draw_h + 6 + vol_chart_h

        chart_w = w - 75
        n = len(self.candles)
        bar_w = max(3, int(chart_w / n * 0.65))

        font = self.font()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        
        painter.setPen(QColor("#38bdf8"))
        parent_win = self.parent()
        while parent_win and not hasattr(parent_win, 'current_commodity'):
            parent_win = parent_win.parent()
        comm_prefix = getattr(parent_win, 'current_commodity', '沪银') if parent_win else '沪银'
        painter.drawText(12, 17, comm_prefix)

        painter.setPen(QColor("#ffffff"))
        painter.drawText(92, 18, "最新: " + self.current_price_str)

        chg_color = QColor("#ef4444") if not self.change_str.startswith("-") else QColor("#22c55e")
        painter.setPen(chg_color)
        painter.drawText(w - 120, 18, self.change_str)

        for i, c in enumerate(self.candles):
            cx = 12 + i * chart_w / max(n, 1) + bar_w / 2
            y_high = pad_top + draw_h - (c["high"] - min_p) / p_range * draw_h
            y_low = pad_top + draw_h - (c["low"] - min_p) / p_range * draw_h
            y_open = pad_top + draw_h - (c["open"] - min_p) / p_range * draw_h
            y_close = pad_top + draw_h - (c["close"] - min_p) / p_range * draw_h

            is_up = c["close"] >= c["open"]
            color = QColor("#ef4444") if is_up else QColor("#22c55e")

            painter.setPen(QPen(color, 1))
            painter.drawLine(int(cx), int(y_high), int(cx), int(y_low))

            body_y = min(y_open, y_close)
            body_h = max(2.0, abs(y_close - y_open))
            painter.setBrush(QBrush(color))
            painter.drawRect(int(cx - bar_w / 2), int(body_y), int(bar_w), int(body_h))

            vol = c.get("volume", 100)
            vol_h = int((vol / max_vol) * vol_chart_h)
            vol_h = max(2, vol_h)
            v_top = vol_base_y - vol_h
            
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRect(int(cx - bar_w / 2), int(v_top), int(bar_w), int(vol_h))

        font.setPointSize(8)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(w - 68, pad_top + 10, f"{max_p:.1f}")
        painter.drawText(w - 68, pad_top + draw_h - 2, f"{min_p:.1f}")
        painter.drawText(w - 68, vol_base_y - vol_chart_h + 8, f"Vol:{max_vol}")

        if 0 <= self.hovered_index < len(self.candles):
            c_data = self.candles[self.hovered_index]
            cx = int(12 + self.hovered_index * chart_w / max(n, 1) + bar_w / 2)

            painter.setPen(QPen(QColor(255, 255, 255, 120), 1, Qt.DashLine))
            painter.drawLine(cx, pad_top, cx, h - pad_bot)

            prev_close = self.candles[self.hovered_index - 1]["close"] if self.hovered_index > 0 else c_data["open"]
            chg_pct = ((c_data["close"] - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            chg_pct_str = f"{chg_pct:+.2f}%"
            item_chg_color = QColor("#ef4444") if chg_pct >= 0 else QColor("#22c55e")

            vol_val = c_data.get("volume", 0)
            display_t = c_data["time"]
            if "02:25" in display_t:
                display_t = display_t.replace("02:25", "02:30 (收盘)")
            lines = [
                (display_t, QColor("#facc15")),
                (f"开盘: {c_data['open']:.1f}", QColor("#ffffff")),
                (f"最高: {c_data['high']:.1f}", QColor("#ffffff")),
                (f"最低: {c_data['low']:.1f}", QColor("#ffffff")),
                (f"收盘: {c_data['close']:.1f}", QColor("#ffffff")),
                (f"成交量: {vol_val}", QColor("#38bdf8")),
                (f"涨幅: {chg_pct_str}", item_chg_color)
            ]

            box_w = 115
            box_h = 120
            box_x = cx + 10 if cx + 10 + box_w < chart_w else cx - box_w - 10
            box_y = pad_top + 5

            painter.setBrush(QBrush(QColor(15, 23, 42, 230)))
            painter.setPen(QPen(QColor(56, 189, 248, 100), 1))
            painter.drawRoundedRect(box_x, box_y, box_w, box_h, 4, 4)

            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)
            ty = box_y + 16
            for text_str, color in lines:
                painter.setPen(color)
                painter.drawText(box_x + 8, ty, text_str)
                ty += 15


class HistorySyncWorker(QObject):
    history_fetched = pyqtSignal(list)
    finished = pyqtSignal()

    def __init__(self, commodity="沪银", period_minutes=5, contract_code="AG2702", data_source="新浪财经 (Sina)"):
        super().__init__()
        self.commodity = commodity
        self.period_minutes = period_minutes
        self.contract_code = contract_code
        self.data_source = data_source
        self.running = True

    def set_target(self, commodity, period_minutes, contract_code="AG2702"):
        self.commodity = commodity
        self.period_minutes = period_minutes
        self.contract_code = contract_code

    def set_data_source(self, data_source):
        self.data_source = data_source

    def stop(self):
        self.running = False

    @pyqtSlot()
    def do_work(self):
        import time
        while self.running:
            try:
                if not check_is_market_open():
                    time.sleep(5)
                    continue
                import akshare as ak
                sym = self.contract_code.lower()
                
                real_candles = []
                if self.period_minutes < 1440:
                    df = ak.futures_zh_minute_sina(symbol=sym, period=str(self.period_minutes))
                    if df is not None and not df.empty:
                        df_recent = df.tail(28)
                        for _, row in df_recent.iterrows():
                            dt_val = str(row.get('datetime', ''))
                            time_display = dt_val[5:16] if len(dt_val) >= 16 else dt_val
                            real_candles.append({
                                "open": float(row['open']),
                                "high": float(row['high']),
                                "low": float(row['low']),
                                "close": float(row['close']),
                                "volume": int(row.get('volume', 100)),
                                "time": time_display
                            })
                else:
                    df = ak.futures_main_sina(symbol=sym.upper())
                    if df is not None and not df.empty:
                        df_recent = df.tail(28)
                        for _, row in df_recent.iterrows():
                            dt_val = str(row.get('date', ''))
                            real_candles.append({
                                "open": float(row['open']),
                                "high": float(row['high']),
                                "low": float(row['low']),
                                "close": float(row['close']),
                                "volume": int(row.get('volume', 1000)),
                                "time": dt_val
                            })
                
                if real_candles:
                    self.history_fetched.emit(real_candles)
            except Exception as e:
                log_error(e, f"HistorySyncWorker [{self.commodity}]")
            
            for _ in range(900):
                if not self.running:
                    break
                time.sleep(1)
        self.finished.emit()


class BaseQuoteSource:
    """行情数据源抽象基类"""
    def get_quote(self, target_type: str) -> dict:
        raise NotImplementedError


class SinaQuoteSource(BaseQuoteSource):
    """新浪财经行情数据源"""
    def get_quote(self, target_type: str) -> dict:
        import time
        now = datetime.datetime.now()
        prefix = "AG" if target_type == "沪银" else "AU"
        headers = {
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        timestamp = int(time.time() * 1000)
        y = now.year % 100
        m = now.month
        prefix_lower = prefix.lower()
        symbols = [f"nf_{prefix}0", f"nf_{prefix_lower}0"]
        for i in range(6):
            target_m = m + i
            target_y = y
            if target_m > 12:
                target_m -= 12
                target_y += 1
            code_str = f"nf_{prefix}{target_y:02d}{target_m:02d}"
            symbols.append(code_str)
            symbols.append(code_str.lower())
        symbols = list(dict.fromkeys(symbols))

        url = f"https://hq.sinajs.cn/list={','.join(symbols)}&_t={timestamp}"
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200:
            for line in resp.text.split(';'):
                if 'hq_str_nf_' in line and '="' in line:
                    parts_split = line.split('="')
                    if len(parts_split) > 1:
                        data_str = parts_split[1].strip('"')
                        if data_str and len(data_str.split(',')) > 13:
                            parts = data_str.split(',')
                            contract = parts[12] if len(parts) > 12 and parts[12] else f"{prefix}2702"
                            latest = float(parts[8]) if len(parts) > 8 and parts[8] else float(parts[2]) if len(parts) > 2 and parts[2] else 12500.0
                            pre_settle = float(parts[3]) if len(parts) > 3 and parts[3] else 0.0
                            change = latest - pre_settle
                            change_pct = (change / pre_settle * 100) if pre_settle > 0 else 0.0
                            volume = parts[11] if len(parts) > 11 else "0"
                            open_interest = parts[10] if len(parts) > 10 else "0"
                            
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

                            display_contract = contract if contract and contract != "0" else f"{prefix}主力"
                            if f"{prefix}0" in line.upper():
                                display_contract = f"{prefix}主力(主连)"

                            return {
                                "contract": display_contract,
                                "price": f"{latest:.1f}",
                                "change": f"{change:+.1f}",
                                "change_pct": f"{change_pct:+.2f}%",
                                "volume": volume,
                                "open_interest": open_interest,
                                "bid1_p": f"{bid1_p:.1f}",
                                "bid1_v": str(bid1_v),
                                "ask1_p": f"{ask1_p:.1f}",
                                "ask1_v": str(ask1_v)
                            }
        raise ValueError("Sina quote fetch failed")


class TencentQuoteSource(BaseQuoteSource):
    """腾讯财经行情数据源"""
    def get_quote(self, target_type: str) -> dict:
        prefix = "AG" if target_type == "沪银" else "AU"
        t_sym = f"f_{prefix.lower()}0"
        url = f"https://qt.gtimg.cn/q={t_sym}"
        headers = {"Referer": "https://finance.qq.com", "User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200 and 'v_' in resp.text:
            parts = resp.text.split('"')[1].split('~')
            if len(parts) > 5:
                contract = parts[2] if parts[2] else f"{prefix}主力"
                latest = float(parts[3]) if parts[3].replace('.','',1).isdigit() else 12523.0
                pre_close = float(parts[4]) if parts[4].replace('.','',1).isdigit() else latest
                change = latest - pre_close
                change_pct = (change / pre_close * 100) if pre_close > 0 else 0.0
                volume = parts[6] if len(parts) > 6 else "1000"
                open_interest = parts[13] if len(parts) > 13 else "50000"
                
                return {
                    "contract": f"{prefix}主力",
                    "price": f"{latest:.1f}",
                    "change": f"{change:+.1f}",
                    "change_pct": f"{change_pct:+.2f}%",
                    "volume": str(volume),
                    "open_interest": str(open_interest),
                    "bid1_p": f"{latest-1.0:.1f}",
                    "bid1_v": "1",
                    "ask1_p": f"{latest+1.0:.1f}",
                    "ask1_v": "1"
                }
        raise ValueError("Tencent quote fetch failed")


class AkShareQuoteSource(BaseQuoteSource):
    """AkShare / Tushare 行情数据源"""
    def get_quote(self, target_type: str) -> dict:
        import akshare as ak
        prefix = "AG" if target_type == "沪银" else "AU"
        sym_code = "ag0" if target_type == "沪银" else "au0"
        df = ak.futures_zh_spot(symbol=sym_code)
        if df is not None and not df.empty:
            row = df.iloc[0]
            latest = float(row.get('settle', row.get('price', 12523.0)))
            pre_settle = float(row.get('pre_settle', latest))
            change = latest - pre_settle
            change_pct = (change / pre_settle * 100) if pre_settle > 0 else 0.0
            return {
                "contract": f"{prefix}主力",
                "price": f"{latest:.1f}",
                "change": f"{change:+.1f}",
                "change_pct": f"{change_pct:+.2f}%",
                "volume": str(row.get('volume', 10000)),
                "open_interest": str(row.get('hold', 50000)),
                "bid1_p": f"{latest-1.0:.1f}",
                "bid1_v": "1",
                "ask1_p": f"{latest+1.0:.1f}",
                "ask1_v": "1"
            }
        raise ValueError("AkShare quote fetch failed")


class EastMoneyQuoteSource(BaseQuoteSource):
    """东方财富行情数据源"""
    def get_quote(self, target_type: str) -> dict:
        prefix = "AG" if target_type == "沪银" else "AU"
        em_secid = "114.AG0" if target_type == "沪银" else "114.AU0"
        url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={em_secid}&fields=f43,f57,f58,f169,f170,f46,f44,f51,f52,f50,f47,f60,f48,f168,f161,f162,f163"
        headers = {"Referer": "https://quote.eastmoney.com", "User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200:
            data = resp.json().get("data")
            if data:
                latest = float(data.get('f43', 125230) / 100.0)
                pre_close = float(data.get('f60', latest))
                change = latest - pre_close
                change_pct = float(data.get('f170', 0.0)) / 100.0
                return {
                    "contract": f"{prefix}主力",
                    "price": f"{latest:.1f}",
                    "change": f"{change:+.1f}",
                    "change_pct": f"{change_pct:+.2f}%",
                    "volume": str(data.get('f47', 10000)),
                    "open_interest": str(data.get('f48', 50000)),
                    "bid1_p": f"{latest-1.0:.1f}",
                    "bid1_v": "1",
                    "ask1_p": f"{latest+1.0:.1f}",
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
    data_fetched = pyqtSignal(dict)
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
            market_open = check_is_market_open()
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
                    self.data_fetched.emit(info)
                    retry_count = 0
                else:
                    retry_count += 1
            except Exception as e:
                log_error(e, f"QuoteWorker [{self.data_source}]")
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
        self.resize(360, 360)
        self.setStyleSheet("background-color: #1e222b; color: white;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("🧮 实时持仓盈亏与佣金计算器")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)

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

        comm_type = getattr(self.parent_window, 'current_commodity', '沪银') if self.parent_window else '沪银'
        base_default = 874.6 if comm_type == "沪金" else 12523.0
        if self.parent_window and hasattr(self.parent_window, 'silver_data'):
            try:
                base_default = float(self.parent_window.silver_data.get('price', base_default))
            except Exception:
                pass

        curr_price = base_default
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            saved_p = self.parent_window.saved_calc_params.get("open_price", None)
            if saved_p is not None:
                if comm_type == "沪金" and saved_p < 3000:
                    curr_price = saved_p
                elif comm_type == "沪银" and saved_p > 3000:
                    curr_price = saved_p

        self.open_price_spin = QDoubleSpinBox()
        self.open_price_spin.setRange(0.1, 999999.0)
        self.open_price_spin.setDecimals(1)
        self.open_price_spin.setValue(curr_price)
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

    def on_param_changed(self):
        self.calculate()
        self.save_current_params()

    def calculate(self):
        try:
            curr_p = 12523.0
            comm_type = "沪银"
            if self.parent_window and hasattr(self.parent_window, 'silver_data'):
                curr_p = float(self.parent_window.silver_data.get('price', 12523.0))
                comm_type = getattr(self.parent_window, 'current_commodity', '沪银')

            mult = 15.0 if comm_type == "沪银" else 1000.0
            mult_unit = "千克/手" if comm_type == "沪银" else "克/手"

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

            self.info_lbl.setText(f"当前{comm_type}现价: {curr_p}  |  乘数: {int(mult)}{mult_unit}")
            self.comm_fee_lbl.setText(f"来回佣金扣除: -{total_commission:.1f} 元 (双边费率: {round_rate*100:.3f}%)")

            if net_pnl >= 0:
                self.pnl_val_lbl.setText(f"净浮盈: +{net_pnl:,.1f} 元")
                self.pnl_val_lbl.setStyleSheet("color: #ef4444; font-size: 18px; font-weight: bold; border: none;")
            else:
                self.pnl_val_lbl.setText(f"净浮亏: {net_pnl:,.1f} 元")
                self.pnl_val_lbl.setStyleSheet("color: #22c55e; font-size: 18px; font-weight: bold; border: none;")
        except Exception:
            pass

    def save_current_params(self):
        if self.parent_window:
            self.parent_window.saved_calc_params = {
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
            self.lock_btn.setText("🔒")
            self.lock_btn.setToolTip("窗口已锁定（无法拖动）")
        else:
            self.lock_btn.setText("🔓")
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
        calc_price = data.get("calc_open_price", 12375.0)
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
            "calc_open_price": self.saved_calc_params.get("open_price", 12375.0),
            "calc_lots": self.saved_calc_params.get("lots", 1),
            "calc_comm_rate": self.saved_calc_params.get("comm_rate", 0.0020)
        }

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
        self.is_forced_exit = False  # 标记是否为真正退出
        self.is_docked = False
        self.normal_geometry = QRect()
        self.current_commodity = "沪银"
        
        self.current_bg_color = "#1e222b"
        self.current_time_color = "#38bdf8"
        self.current_card_bg = "#262b36"
        self.current_accent = "#0284c7"

        self.water_enabled = True
        self.water_interval_min = 45
        self.sport_enabled = True
        self.sport_interval_min = 90

        self.saved_calc_params = {"dir_idx": 1, "open_price": 12375.0, "lots": 1, "comm_rate": 0.0020}
        self.silver_data = {
            "contract": "AG2702",
            "price": "12523.0",
            "change": "-52.0",
            "change_pct": "-0.41%",
            "volume": "366524",
            "open_interest": "242022",
            "bid1_p": "12522.0",
            "bid1_v": "1",
            "ask1_p": "12524.0",
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
        c_layout.setContentsMargins(16, 12, 16, 16)
        c_layout.setSpacing(8)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        
        self.lock_btn = QPushButton("🔒")
        self.lock_btn.setFixedSize(28, 28)
        self.lock_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; font-size: 14px; }
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

        self.time_label = QLabel("21:29:27")
        self.time_label.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.time_label)

        self.date_label = QLabel("2026年11月06日 星期五")
        self.date_label.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.date_label)

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
        self.stock_status_label = QLabel("● 股市：已收盘")
        self.stock_status_label.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        
        self.cal_btn = QPushButton("📅 休市日历")
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

        self.silver_status_label = QLabel("● 白银期货：交易中 (Live)")
        self.silver_status_label.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        status_layout.addWidget(self.silver_status_label)

        c_layout.addWidget(self.status_card)

        comm_row = QHBoxLayout()
        comm_label = QLabel("📌 品种:")
        comm_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        
        self.comm_combo = QComboBox()
        self.comm_combo.addItems(["沪银主力 (AG2702)", "沪金主力 (AU2702)"])
        self.ag_contract = "AG2702"
        self.au_contract = "AU2702"
        self.comm_combo.setStyleSheet("""
            QComboBox {
                background-color: #262b36; color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 4px; padding: 3px 6px; font-size: 11px; font-weight: bold;
            }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 12px; border-left-width: 0px; }
            QComboBox QAbstractItemView { background-color: #1e222b; color: #38bdf8; selection-background-color: #0284c7; selection-color: #ffffff; }
        """)
        self.comm_combo.currentIndexChanged.connect(self.on_commodity_changed)
        
        comm_row.addWidget(comm_label)
        comm_row.addWidget(self.comm_combo)
        comm_row.addStretch()
        c_layout.addLayout(comm_row)

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

        self.trend_chart = MiniTrendChartWidget(self)
        self.trend_chart.period_changed.connect(self.on_chart_period_changed)
        c_layout.addWidget(self.trend_chart)

        self.next_holiday_label = QLabel("📌 距离下一节假日：元旦 (56天)")
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
        self.current_commodity = "沪银"
        
        self.quote_thread = QThread()
        self.quote_worker = CommodityQuoteWorker("沪银", "新浪财经 (Sina)")
        self.quote_worker.moveToThread(self.quote_thread)
        self.quote_thread.started.connect(self.quote_worker.do_work)
        self.quote_worker.data_fetched.connect(self.on_silver_data_updated)
        self.quote_thread.start()

        self.history_thread = QThread()
        self.history_worker = HistorySyncWorker(self.current_commodity, self.trend_chart.period_minutes, self.ag_contract, "新浪财经 (Sina)")
        self.history_worker.moveToThread(self.history_thread)
        self.history_thread.started.connect(self.history_worker.do_work)
        self.history_worker.history_fetched.connect(self.on_history_candles_updated)
        self.history_thread.start()

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
        msg = f"已连续专注 {self.water_interval_min} 分钟啦！\n💡 记得及时补充温水，保持身体活力哦~"
        dlg = SilentTipDialog("💧 健康饮水提醒", msg, self)
        dlg.exec_()

    def show_sport_reminder(self):
        try:
            for _ in range(3):
                winsound.Beep(1200, 200)
                import time
                time.sleep(0.1)
        except Exception:
            pass
        msg = f"已久坐满 {self.sport_interval_min} 分钟啦！\n🏃 站起来活动一下筋骨、伸个懒腰，眺望远方休息一下吧！"
        dlg = SilentTipDialog("🏃 久坐运动提醒", msg, self)
        dlg.exec_()

    def on_chart_period_changed(self, new_period):
        if hasattr(self, 'history_worker'):
            self.history_worker.set_target(self.current_commodity, new_period)

    def on_history_candles_updated(self, candles):
        if candles:
            self.trend_chart.candles = candles
            self.trend_chart.save_candles_to_cache()
            self.trend_chart.update()

    def on_source_changed(self, index):
        sources = ["新浪财经 (Sina)", "腾讯财经 (Tencent)", "Tushare 数据", "AkShare", "东方财富 (EastMoney)"]
        selected_source = sources[index] if 0 <= index < len(sources) else "新浪财经 (Sina)"
        if hasattr(self, 'quote_worker'):
            self.quote_worker.set_data_source(selected_source)
        if hasattr(self, 'history_worker'):
            self.history_worker.set_data_source(selected_source)

    def on_commodity_changed(self, index):
        self.current_commodity = "沪银" if index == 0 else "沪金"
        if self.current_commodity == "沪金":
            self.silver_data["contract"] = self.au_contract
            self.silver_data["price"] = "874.6"
            self.silver_data["change"] = "-0.3"
            self.silver_data["change_pct"] = "-0.03%"
            self.silver_data["bid1_p"] = "874.6"
            self.silver_data["ask1_p"] = "875.6"
            self.trend_chart.current_price_str = "874.6"
            self.trend_chart.change_str = "-0.03%"
        else:
            self.silver_data["contract"] = self.ag_contract
            self.silver_data["price"] = "12576.0"
            self.silver_data["change"] = "-44.0"
            self.silver_data["change_pct"] = "-0.35%"
            self.silver_data["bid1_p"] = "12522.0"
            self.silver_data["ask1_p"] = "12524.0"
            self.trend_chart.current_price_str = "12576.0"
            self.trend_chart.change_str = "-0.35%"
        
        self.update_silver_board_ui()
        self.trend_chart.load_candles_from_cache_or_default()
        
        contract_code = self.ag_contract if self.current_commodity == "沪银" else self.au_contract
        if hasattr(self, 'quote_worker'):
            self.quote_worker.set_target(self.current_commodity)
        if hasattr(self, 'history_worker'):
            self.history_worker.set_target(self.current_commodity, self.trend_chart.period_minutes, contract_code)

    def update_compact_pnl(self):
        try:
            comm_type = getattr(self, 'current_commodity', '沪银')
            curr_p = 874.6 if comm_type == "沪金" else 12523.0
            if hasattr(self, 'silver_data') and self.silver_data:
                try:
                    curr_p = float(self.silver_data.get('price', curr_p))
                except Exception:
                    pass
            
            mult = 15.0 if comm_type == "沪银" else 1000.0

            p_data = getattr(self, 'saved_calc_params', {"dir_idx": 1, "open_price": curr_p, "lots": 1, "comm_rate": 0.0020})
            open_p = p_data.get("open_price", curr_p)
            lots = p_data.get("lots", 1)
            dir_idx = p_data.get("dir_idx", 1)
            is_long = (dir_idx == 0)

            if hasattr(self, 'compact_open_lbl'):
                dir_str = "多头" if is_long else "空头"
                self.compact_open_lbl.setText(f"{dir_str}开仓价: {open_p:.1f}  ({lots}手)")

            diff = (curr_p - open_p) if is_long else (open_p - curr_p)
            gross_pnl = diff * mult * lots

            single_rate = p_data.get("comm_rate", 0.0020) / 100.0
            round_rate = single_rate * 2.0

            turnover = (open_p + curr_p) * mult * lots
            total_commission = turnover * single_rate

            net_pnl = gross_pnl - total_commission

            if hasattr(self, 'compact_comm_lbl'):
                self.compact_comm_lbl.setText(f"来回佣金扣除: -{total_commission:.1f} 元 (双边费率: {round_rate*100:.3f}%)")

            if hasattr(self, 'compact_pnl_val_lbl'):
                if net_pnl >= 0:
                    self.compact_pnl_val_lbl.setText(f"净浮盈: +{net_pnl:,.1f} 元")
                    self.compact_pnl_val_lbl.setStyleSheet("color: #ef4444; font-size: 15px; font-weight: bold; border: none; background: transparent;")
                else:
                    self.compact_pnl_val_lbl.setText(f"净浮亏: {net_pnl:,.1f} 元")
                    self.compact_pnl_val_lbl.setStyleSheet("color: #22c55e; font-size: 15px; font-weight: bold; border: none; background: transparent;")
        except Exception as e:
            log_error(e, "UpdateCompactPnL")

    def on_silver_data_updated(self, info):
        if not self.is_market_open(datetime.datetime.now()):
            return
        self.silver_data.update(info)
        contract = info.get("contract", "")
        if contract and "主连" not in contract and len(contract) >= 5:
            if self.current_commodity == "沪银":
                self.ag_contract = contract
            else:
                self.au_contract = contract
            if hasattr(self, 'history_worker'):
                self.history_worker.set_target(self.current_commodity, self.trend_chart.period_minutes, contract)
            
            curr_idx = self.comm_combo.currentIndex()
            self.comm_combo.blockSignals(True)
            self.comm_combo.setItemText(0, f"沪银主力 ({self.ag_contract})")
            self.comm_combo.setItemText(1, f"沪金主力 ({self.au_contract})")
            self.comm_combo.setCurrentIndex(curr_idx)
            self.comm_combo.blockSignals(False)

        self.update_silver_board_ui()
        self.trend_chart.update_latest_price(info.get("price"), info.get("change_pct"))
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
                            cond_desc = f"价格涨至 {target}" if cond_type == "up" else f"价格跌至 {target}"
                            msg = f"价格已到预警线！合约 {current_contract}\n当前最新价: {current_price}\n条件: {cond_desc}"
                            
                            try:
                                import time
                                for _ in range(3):
                                    winsound.Beep(1200, 350)
                                    time.sleep(0.15)
                            except Exception:
                                pass

                            dlg = SilentTipDialog("价格预警触发 (价格已到预警线)", msg, self)
                            dlg.exec_()
            
            if updated:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(alerts, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def update_silver_board_ui(self):
        d = self.silver_data
        try:
            chg_val = float(d['change'])
            curr_p = float(d['price'])
        except Exception:
            chg_val = 0.0
            curr_p = 12523.0
        
        color_hex = "#ef4444" if chg_val >= 0 else "#22c55e"
        arrow = "▲" if chg_val >= 0 else "▼"
        
        contract_name = d.get('contract', 'AG主力')
        comm_prefix = getattr(self, 'current_commodity', '沪银')
        step = 1.0 if comm_prefix == "沪银" else 0.2

        ask_prices = [curr_p + step * i for i in range(5, 0, -1)]
        bid_prices = [curr_p - step * i for i in range(1, 6)]
        
        ask_vols = [d.get(f'ask{i}_v', str(random.randint(2, 25))) for i in range(5, 0, -1)]
        bid_vols = [d.get(f'bid{i}_v', str(random.randint(2, 25))) for i in range(1, 6)]
        
        ask_rows = ""
        for idx, (p, v) in enumerate(zip(ask_prices, ask_vols)):
            level = 5 - idx
            ask_rows += f'''
            <tr>
                <td style="font-size: 11px; color: #22c55e; padding: 1px 6px;">卖{level} &nbsp; {p:.1f}</td>
                <td></td>
                <td align="right" style="font-size: 11px; color: #22c55e; padding: 1px 6px;">{v}手</td>
            </tr>'''

        bid_rows = ""
        for idx, (p, v) in enumerate(zip(bid_prices, bid_vols)):
            level = idx + 1
            bid_rows += f'''
            <tr>
                <td style="font-size: 11px; color: #ef4444; padding: 1px 6px;">买{level} &nbsp; {p:.1f}</td>
                <td></td>
                <td align="right" style="font-size: 11px; color: #ef4444; padding: 1px 6px;">{v}手</td>
            </tr>'''

        open_interest_str = d.get('open_interest', '0')
        try:
            total_oi = int(float(open_interest_str))
        except Exception:
            total_oi = 242022
            
        ratio_long = 0.51 if chg_val >= 0 else 0.49
        long_oi = int(total_oi * ratio_long)
        short_oi = total_oi - long_oi
        
        html_text = f"""
        <table width="100%" cellspacing="0" cellpadding="0" style="font-family: Consolas, monospace; background-color: #141820; border-radius: 8px; padding: 2px;">
            <tr>
                <td style="font-size: 11px; font-weight: bold; color: #94a3b8; padding: 4px 6px;">{comm_prefix} {contract_name}</td>
                <td align="center" style="font-size: 15px; font-weight: bold; color: #ffffff; padding: 4px 6px;">{d['price']}</td>
                <td align="right" style="font-size: 11px; font-weight: bold; color: {color_hex}; padding: 4px 6px;">{arrow} {d['change_pct']}</td>
            </tr>
            <tr>
                <td colspan="3" style="border-top: 1px solid rgba(255,255,255,0.08); padding: 1px 0px;"></td>
            </tr>
            {ask_rows}
            <tr>
                <td colspan="3" style="border-top: 1px stroke rgba(255,255,255,0.05); padding: 1px 0px;"></td>
            </tr>
            {bid_rows}
            <tr>
                <td colspan="3" style="border-top: 1px solid rgba(255,255,255,0.08); padding: 3px 6px; font-size: 11px;">
                    <span style="color: #38bdf8;">📊 总持仓:</span> <span style="color: #ffffff; font-weight: bold;">{total_oi:,}</span> &nbsp;|&nbsp; 
                    <span style="color: #ef4444;">买多: {long_oi:,}</span> &nbsp;|&nbsp; 
                    <span style="color: #22c55e;">卖空: {short_oi:,}</span>
                </td>
            </tr>
        </table>
        """
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
        """拦截右上角关闭按钮事件，实现最小化到托盘或安全退出"""
        if self.is_forced_exit:
            self.save_settings()
            event.accept()  # 真正关闭
        else:
            # 如果是正常点击 ✕，隐藏窗口进入系统托盘常驻
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
        """托盘菜单专属的“彻底退出”函数"""
        self.is_forced_exit = True
        self.save_settings()
        
        if hasattr(self, 'quote_worker'):
            self.quote_worker.stop()
        if hasattr(self, 'history_worker'):
            self.history_worker.stop()

        if hasattr(self, 'quote_thread'):
            self.quote_thread.quit()
            self.quote_thread.wait(2000)

        if hasattr(self, 'history_thread'):
            self.history_thread.quit()
            self.history_thread.wait(2000)

        self.tray_icon.hide()
        QApplication.quit()

    def apply_theme(self, bg_color, time_color, card_bg, accent):
        self.current_bg_color = bg_color
        self.current_time_color = time_color
        self.current_card_bg = card_bg
        self.current_accent = accent

        self.container.setStyleSheet(f"""
            QWidget#MainContainer {{
                background-color: {bg_color};
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.15);
            }}
        """)

        self.time_label.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg}; color: #94a3b8; font-size: 28px; font-weight: bold; font-family: Consolas, monospace; border-radius: 8px; padding: 6px; border: 1px solid rgba(255,255,255,0.06);
            }}
        """)

        self.date_label.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg}; color: #94a3b8; font-size: 13px; border-radius: 8px; padding: 5px; border: 1px solid rgba(255,255,255,0.06);
            }}
        """)

        self.silver_board.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg}; border-radius: 8px; padding: 4px; border: 1px solid rgba(255,255,255,0.06);
            }}
        """)

        self.status_card.setStyleSheet(f"""
            QWidget {{
                background-color: {card_bg}; border-radius: 8px; border: 1px solid rgba(255,255,255,0.06);
            }}
        """)

        self.next_holiday_label.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg}; color: #38bdf8; font-size: 12px; font-weight: bold; border-radius: 8px; padding: 5px; border: 1px solid rgba(56, 189, 248, 0.2);
            }}
        """)

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
            self.lock_btn.setText("🔒")
            self.lock_btn.setToolTip("窗口已锁定（无法拖动）")
        else:
            self.lock_btn.setText("🔓")
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
        
        self.time_label.setText(now.strftime("%H:%M:%S"))
        self.date_label.setText(now.strftime("%Y年%m月%d日") + " " + week_days[now.weekday()])

        self.update_next_holiday(now)
        self.update_macro_countdown(now)

        date_key = now.strftime("%Y-%m-%d")
        holiday_info = HOLIDAY_SCHEDULE.get(date_key, None)

        if holiday_info:
            types = holiday_info.get("types", []) if isinstance(holiday_info, dict) else holiday_info
            reason = holiday_info.get("reason", "休市") if isinstance(holiday_info, dict) else "休市"
            
            if "A" in types:
                self.stock_status_label.setText(f"● 股市：{reason}")
            else:
                self.stock_status_label.setText("● 股市：交易中")

            if "AG" in types:
                short_name = "白银" if getattr(self, 'current_commodity', '沪银') == "沪银" else "黄金"
                self.silver_status_label.setText(f"● {short_name}：{reason}")
            else:
                self.update_silver_countdown(now)
        elif now.weekday() >= 5:
            self.stock_status_label.setText("● 股市：周末休市")
            short_name = "白银" if getattr(self, 'current_commodity', '沪银') == "沪银" else "黄金"
            self.silver_status_label.setText(f"● {short_name}：周末休市 (非交易日)")
        else:
            t = now.time()
            if datetime.time(9, 30) <= t <= datetime.time(15, 0):
                self.stock_status_label.setText("● 股市：交易中")
            else:
                self.stock_status_label.setText("● 股市：已收盘")
            
            self.update_silver_countdown(now)

    def update_silver_countdown(self, now):
        current_time = now.time()
        comm_prefix = getattr(self, 'current_commodity', '沪银')
        market_name = "白银期货" if comm_prefix == "沪银" else "黄金期货"
        short_name = "白银" if comm_prefix == "沪银" else "黄金"
        
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
        elif current_time >= datetime.time(21, 0):
            is_trading = True
            closing_dt = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), t_night_close)
        elif current_time <= datetime.time(2, 30):
            is_trading = True
            closing_dt = datetime.datetime.combine(now.date(), t_night_close)

        if is_trading and closing_dt:
            diff = closing_dt - now
            if diff.total_seconds() > 0:
                hours = int(diff.total_seconds() // 3600)
                minutes = int((diff.total_seconds() % 3600) // 60)
                seconds = int(diff.total_seconds() % 60)
                if hours > 0:
                    time_str = f"{hours:02d}小时{minutes:02d}分{seconds:02d}秒"
                else:
                    time_str = f"{minutes:02d}分{seconds:02d}秒"
                self.silver_status_label.setText(f"● {market_name}：交易中 (距闭市 {time_str})")
            else:
                self.silver_status_label.setText(f"● {market_name}：即将闭市...")
        else:
            next_open = datetime.datetime.combine(now.date(), t_morning_open)
            if current_time > datetime.time(15, 0) and current_time < datetime.time(21, 0):
                next_open = datetime.datetime.combine(now.date(), t_night_open)
            elif current_time >= datetime.time(2, 30) and current_time < datetime.time(9, 0):
                next_open = datetime.datetime.combine(now.date(), t_morning_open)
            elif current_time > datetime.time(11, 30) and current_time < datetime.time(13, 30):
                next_open = datetime.datetime.combine(now.date(), datetime.time(13, 30))
            else:
                if current_time >= datetime.time(21, 0):
                    next_open = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), t_morning_open)
                else:
                    next_open = datetime.datetime.combine(now.date(), t_morning_open)

            diff = next_open - now
            if diff.total_seconds() > 0:
                hours = int(diff.total_seconds() // 3600)
                minutes = int((diff.total_seconds() % 3600) // 60)
                seconds = int(diff.total_seconds() % 60)
                self.silver_status_label.setText(f"● {short_name}非交易时段 (距开盘 {hours:02d}:{minutes:02d}:{seconds:02d})")
            else:
                self.silver_status_label.setText(f"● {short_name}即将开盘...")

    def update_macro_countdown(self, now):
        upcoming = []
        for ev in MACRO_EVENTS:
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
                secs = total_sec % 60
                
                if days > 0:
                    time_str = f"{days}天 {hours:02d}时{mins:02d}分"
                else:
                    time_str = f"{hours:02d}时{mins:02d}分{secs:02d}秒"
                
                name_str = ev["name"]
                icon = "📊" if "CPI" in name_str else "👥" if "非农" in name_str else "🏛️"
                
                rows_html += f'''
                <tr>
                    <td style="font-size: 11px; color: #e2e8f0; padding: 2px 4px;">{icon} {name_str}</td>
                    <td align="right" style="font-size: 11px; font-weight: bold; color: #38bdf8; padding: 2px 4px;">{time_str}</td>
                </tr>'''

            html_text = f"""
            <table width="100%" cellspacing="0" cellpadding="0" style="font-family: Consolas, monospace; background-color: #141820; border-radius: 8px; padding: 4px;">
                <tr>
                    <td colspan="2" style="font-size: 11px; font-weight: bold; color: #facc15; padding: 2px 4px 4px 4px; border-bottom: 1px solid rgba(255,255,255,0.08);">⚡ 核心宏观大事件倒计时看板</td>
                </tr>
                {rows_html}
            </table>
            """
            self.macro_board.setText(html_text)
        else:
            self.macro_board.setText("⚡ 宏观事件：暂无近期安排")

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
            self.next_holiday_label.setText(f"📌 距离下一节假日：{clean_reason} ({days_diff}天)")
        else:
            self.next_holiday_label.setText("📌 距离下一节假日：暂无近期安排")

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
        single_instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        single_instance_socket.bind(('127.0.0.1', 49832))
        single_instance_socket.listen(1)
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
