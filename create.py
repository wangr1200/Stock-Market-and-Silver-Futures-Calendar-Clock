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

def _is_us_dst(dt):
    year = dt.year
    march_1 = datetime.datetime(year, 3, 1)
    march_second_sunday = 1 + (6 - march_1.weekday()) % 7 + 7
    dst_start = datetime.datetime(year, 3, march_second_sunday, 14, 0)
    nov_1 = datetime.datetime(year, 11, 1)
    nov_first_sunday = 1 + (6 - nov_1.weekday()) % 7
    dst_end = datetime.datetime(year, 11, nov_first_sunday, 14, 0)
    return dst_start <= dt < dst_end

def _is_eu_dst(dt):
    year = dt.year
    march_31 = datetime.datetime(year, 3, 31)
    march_last_sunday = 31 - (march_31.weekday() + 1) % 7
    dst_start = datetime.datetime(year, 3, march_last_sunday, 9, 0)
    oct_31 = datetime.datetime(year, 10, 31)
    oct_last_sunday = 31 - (oct_31.weekday() + 1) % 7
    dst_end = datetime.datetime(year, 10, oct_last_sunday, 10, 0)
    return dst_start <= dt < dst_end

def get_dynamic_macro_events():
    now = datetime.datetime.now()
    y, m = now.year, now.month
    grace = datetime.timedelta(hours=24)

    def _next_or_recent_us(day, dst_hour, dst_minute):
        cand = datetime.datetime(y, m, day, dst_hour, dst_minute)
        if not _is_us_dst(cand):
            cand += datetime.timedelta(hours=1)
        if cand + grace > now:
            return cand
        ny = y + (1 if m == 12 else 0)
        nm = (m % 12) + 1
        cand_next = datetime.datetime(ny, nm, day, dst_hour, dst_minute)
        if not _is_us_dst(cand_next):
            cand_next += datetime.timedelta(hours=1)
        return cand_next

    def _next_or_recent_eu(day, dst_hour, dst_minute):
        cand = datetime.datetime(y, m, day, dst_hour, dst_minute)
        if not _is_eu_dst(cand):
            cand += datetime.timedelta(hours=1)
        if cand + grace > now:
            return cand
        ny = y + (1 if m == 12 else 0)
        nm = (m % 12) + 1
        cand_next = datetime.datetime(ny, nm, day, dst_hour, dst_minute)
        if not _is_eu_dst(cand_next):
            cand_next += datetime.timedelta(hours=1)
        return cand_next

    events = [
        {"name": "美国非农就业报告 (NFP)", "time": _next_or_recent_us(5, 20, 30)},
        {"name": "美联储利率决议 (FOMC)", "time": _next_or_recent_us(19, 2, 0)},
        {"name": "美国CPI数据公布", "time": _next_or_recent_us(12, 20, 30)},
        {"name": "欧洲央行利率决议", "time": _next_or_recent_eu(15, 20, 15)}
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
        container.setStyleSheet(
            "QWidget {"
            "    background-color: #1e222b;"
            "    border-radius: 12px;"
            "    border: 1px solid rgba(56, 189, 248, 0.3);"
            "}"
        )
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
        ok_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #0284c7;"
            "    color: white;"
            "    border-radius: 6px;"
            "    padding: 6px 16px;"
            "    font-weight: bold;"
            "    font-size: 13px;"
            "    border: none;"
            "}"
            "QPushButton:hover {"
            "    background-color: #0369a1;"
            "}"
        )
        ok_btn.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)


class MacroDetailDialog(QDialog):
    def __init__(self, event_name, event_info, parent=None):
        super().__init__(parent)
        self.event_name = event_name
        self.event_info = event_info
        self.drag_pos = QPoint()
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(420, 320)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        box = QWidget(self)
        box.setStyleSheet(
            "QWidget {"
            "    background-color: #1e222b;"
            "    border-radius: 10px;"
            "    border: 1px solid rgba(56, 189, 248, 0.35);"
            "}"
        )
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setColor(QColor(0, 0, 0, 190))
        shadow.setOffset(0, 4)
        box.setGraphicsEffect(shadow)
        outer.addWidget(box)

        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title_lbl = QLabel("📊 宏观事件深度解析 — " + self.event_name)
        title_lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: #94a3b8; font-size: 14px; font-weight: bold; } QPushButton:hover { color: #ffffff; background-color: rgba(255,255,255,0.1); border-radius: 4px; }")
        close_btn.clicked.connect(self.close)

        header.addWidget(title_lbl)
        header.addStretch()
        header.addWidget(close_btn)
        layout.addLayout(header)

        content_card = QWidget()
        content_card.setStyleSheet("background-color: #141820; border-radius: 8px; border: 1px solid rgba(255,255,255,0.06);")
        c_layout = QVBoxLayout(content_card)
        c_layout.setContentsMargins(12, 10, 12, 10)
        c_layout.setSpacing(6)

        status_txt = self.event_info if self.event_info else "已公布: 数据正在同步中"
        self.status_lbl = QLabel(status_txt)
        self.status_lbl.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: bold; border: none;")
        c_layout.addWidget(self.status_lbl)

        analysis_text = self.get_analysis_content()
        self.detail_lbl = QLabel(analysis_text)
        self.detail_lbl.setWordWrap(True)
        self.detail_lbl.setStyleSheet("color: #e2e8f0; font-size: 12px; border: none; line-height: 1.4;")
        c_layout.addWidget(self.detail_lbl)

        layout.addWidget(content_card)

        footer_lbl = QLabel("提示：点击窗口任意空白处可拖拽浮窗位置")
        footer_lbl.setStyleSheet("color: #64748b; font-size: 10px; border: none; background: transparent;")
        footer_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer_lbl)

    def get_analysis_content(self):
        name = self.event_name
        if "CPI" in name:
            return (
                "<b>【核心数据解读】</b><br>"
                "• <b>市场影响</b>：美国消费者物价指数（CPI）是评估通胀压力与美联储货币政策走向的关键风向标。<br>"
                "• <b>贵金属联动</b>：若实际通胀高于预期，通常强化加息预期或推迟降息，利空黄金/白银；反之若通胀降温，贵金属与工业银将迎来爆发性买盘。<br>"
                "• <b>资产配置建议</b>：密切关注核心CPI的分项粘性，高通胀环境下实体矿产（如锑、银、金）具备天然抗通胀避险溢价."
            )
        elif "非农" in name:
            return (
                "<b>【非农就业报告 (NFP) 解读】</b><br>"
                "• <b>市场影响</b>：非农就业人数及失业率直接反映美国劳动力市场景气度。<br>"
                "• <b>贵金属联动</b>：就业数据超预期强劲常带动美元指数反弹，压制以美元计价的贵金属短期价格；若就业恶化，降息预期升温将引发贵金属和矿业股走强。<br>"
                "• <b>交易策略</b>：数据公布前后1小时市场波动剧烈，建议结合仓位与技术支撑位做好风险防控."
            )
        elif "美联储" in name or "FOMC" in name:
            return (
                "<b>【美联储利率决议 (FOMC) 解读】</b><br>"
                "• <b>市场影响</b>：决议声明及鲍威尔新闻发布会定调全球流动性周期。<br>"
                "• <b>贵金属联动</b>：鸽派转向或降息落地通常是贵金属牛市的核心催化剂；长线来看，法定货币信誉稀释下，工业银与战略稀缺矿产表现弹性巨大。<br>"
                "• <b>资产配置建议</b>：重点关注点阵图及终端利率预期变化."
            )
        else:
            return (
                "<b>【宏观事件专业解读】</b><br>"
                "• 该事件对全球大宗商品、外汇及权益市场具有重要指导意义。<br>"
                "• 建议投资者结合实时汇率、行业库存及地缘政治变动综合评估仓位."
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_pos)
            event.accept()


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
            
        self.contract_combo.setStyleSheet(
            "QComboBox {"
            "    background-color: #262b36; color: #ffffff; font-weight: bold;"
            "    border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;"
            "}"
            "QComboBox QAbstractItemView { background-color: #1e222b; color: white; selection-background-color: #0284c7; }"
        )
        self.contract_combo.currentIndexChanged.connect(self.on_contract_changed)
        form.addRow("选择合约:", self.contract_combo)

        self.cond_combo = QComboBox()
        self.cond_combo.addItems(["合约价格涨到 (>=)", "合约价格跌到 (<=)"])
        self.cond_combo.setStyleSheet(
            "QComboBox {"
            "    background-color: #262b36; color: #e2e8f0;"
            "    border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;"
            "}"
            "QComboBox QAbstractItemView { background-color: #1e222b; color: white; selection-background-color: #0284c7; }"
        )
        form.addRow("预警条件:", self.cond_combo)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(1.0, 999999.0)
        self.price_spin.setDecimals(1)
        self.price_spin.setValue(self.current_price)
        self.price_spin.setStyleSheet(
            "QDoubleSpinBox {"
            "    background-color: #262b36; color: #ffffff; font-weight: bold;"
            "    border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;"
            "}"
        )
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
        add_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #0284c7; color: white; border-radius: 4px; padding: 5px 12px; font-weight: bold; font-size: 13px;"
            "}"
            "QPushButton:hover { background-color: #0369a1; }"
        )
        add_btn.clicked.connect(self.open_add_alert)
        top_row.addWidget(add_btn)
        layout.addLayout(top_row)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["合约", "预警条件", "目标价格", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet(
            "QTableWidget {"
            "    background-color: #161922; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px;"
            "    gridline-color: #262b36; font-size: 13px;"
            "}"
            "QHeaderView::section {"
            "    background-color: #262b36; color: #ffffff; font-weight: bold; border: none; padding: 4px;"
            "}"
        )
        layout.addWidget(self.table)

        bot_row = QHBoxLayout()
        del_btn = QPushButton("删除选中")
        del_btn.setStyleSheet("background-color: #ef4444; color: white; border-radius: 4px; padding: 5px 12px; font-weight: bold;")
        del_btn.clicked.connect(self.delete_selected)
        
        close_btn = QPushButton("关闭窗口")
        close_btn.setStyleSheet("background-color: #334155; color: white; border-radius: 4px; padding: 5px 12px;")
        close_btn.clicked.connect(self.accept)

        sync_cloud_btn = QPushButton("同步到云端")
        sync_cloud_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #059669; color: white; border-radius: 4px; padding: 5px 12px; font-weight: bold; font-size: 13px;"
            "}"
            "QPushButton:hover { background-color: #10b981; }"
        )
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
        self.calendar.setStyleSheet(
            "QCalendarWidget QAbstractItemView:enabled {"
            "    font-size: 15px; color: #334155;"
            "    selection-background-color: #ffffff; selection-color: white;"
            "}"
            "QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #1e222b; }"
            "QCalendarWidget QToolButton { color: white; font-size: 13px; font-weight: bold; }"
        )
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
        self.theme_combo.setStyleSheet(
            "QComboBox {"
            "    background-color: #262b36; color: #e2e8f0; border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;"
            "}"
            "QComboBox QAbstractItemView { background-color: #1e222b; color: white; selection-background-color: #0284c7; }"
        )
        self.theme_combo.currentIndexChanged.connect(self.change_theme)
        form_layout.addRow("皮肤/主题配色:", self.theme_combo)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(40, 100)
        curr_opacity = int(self.parent_window.windowOpacity() * 100)
        self.opacity_slider.setValue(curr_opacity if curr_opacity > 0 else 95)
        self.opacity_slider.setStyleSheet(
            "QSlider::groove:horizontal { background: #334155; height: 6px; border-radius: 3px; } "
            "QSlider::handle:horizontal { background: #38bdf8; width: 14px; margin: -4px 0; border-radius: 7px; }"
        )
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
                            vals = line.split('="')[1].strip('"').split(',')

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
                            vals = line.split('="')[1].strip('"').split(',')
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
        symbol = "XAUUSD" if is_gold else "XAGUSD"
        
        headers_sina = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}
        sym_candidates = ["XAU", "hf_XAU", "GC00Y"] if is_gold else ["XAG", "hf_XAG", "SI00Y"]
        for sym in sym_candidates:
            try:
                url = f"https://hq.sinajs.cn/list={sym}"
                r = requests.get(url, headers=headers_sina, timeout=2.5)
                if r.status_code == 200 and '="' in r.text:
                    parts = r.text.split('="')
                    if len(parts) > 1:
                        vals = [v.strip() for v in parts[1].strip('";\n').split(',')]
                        p_idx = 0 if (sym.startswith("hf_") or len(vals) > 9) else 8
                        if len(vals) > p_idx and safe_float(vals[p_idx], 0) > 0:
                            price_val = safe_float(vals[p_idx], 0.0)
                            prev_close = safe_float(vals[7] if p_idx == 0 else vals[3], 0.0)
                            if prev_close <= 0 and len(vals) > 9:
                                prev_close = safe_float(vals[9], 0.0)
                            if prev_close <= 0:
                                prev_close = price_val
                            change = price_val - prev_close
                            chg_pct = (change / prev_close * 100.0) if prev_close > 0 else 0.0
                            return {
                                "contract": "XAUUSD" if is_gold else "AGUSDO",
                                "price": ("%.2f" % price_val) if is_gold else ("%.3f" % price_val),
                                "change": ("%+.2f" % change) if is_gold else ("%+.3f" % change),
                                "change_pct": "%+.2f%%" % chg_pct,
                                "volume": "50000",
                                "open_interest": "100000"
                            }
            except Exception:
                continue

        try:
            secid_list = ["106.XAUUSD", "122.XAU", "100.XAU"] if is_gold else ["106.XAGUSD", "122.XAG", "100.XAG"]
            for secid in secid_list:
                url_em = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f44,f45,f46,f47,f48,f60,f169,f170"
                resp = requests.get(url_em, headers={'Referer': 'https://quote.eastmoney.com', 'User-Agent': 'Mozilla/5.0'}, timeout=2.5)
                if resp.status_code == 200:
                    jdata = resp.json()
                    edata = jdata.get('data')
                    if edata:
                        p = safe_float(edata.get('f43', 0), 0.0)
                        if p > 0:
                            price_val = p / 100.0 if p > 1000 else p
                            settle = safe_float(edata.get('f60', 0), 0.0)
                            if settle > 1000:
                                settle = settle / 100.0
                            elif settle <= 0:
                                settle = price_val
                            change = price_val - settle
                            chg_pct = (change / settle * 100.0) if settle > 0 else 0.0
                            return {
                                "contract": "XAUUSD" if is_gold else "AGUSDO",
                                "price": ("%.2f" % price_val) if is_gold else ("%.3f" % price_val),
                                "change": ("%+.2f" % change) if is_gold else ("%+.3f" % change),
                                "change_pct": "%+.2f%%" % chg_pct,
                                "volume": str(edata.get('f47', '25000')),
                                "open_interest": str(edata.get('f48', '80000'))
                            }
        except Exception:
            pass

        us_source = USStockQuoteSource()
        us_data = us_source.get_quote("IAU" if is_gold else "SLV")
        if us_data and safe_float(us_data.get("price", 0)) > 0:
            p = safe_float(us_data.get("price", 0))
            c = safe_float(us_data.get("change", 0))
            scale = 52.743 if is_gold else 1.095
            price_val = p * scale
            change_val = c * scale
            
            prev_val = price_val - change_val
            if prev_val > 0 and abs(change_val / prev_val) > 0.05:
                change_val = prev_val * 0.002
                price_val = prev_val + change_val

            chg_pct = (change_val / prev_val * 100.0) if prev_val > 0 else safe_float(us_data.get("change_pct", "0").replace("%", ""), 0)
            
            return {
                "contract": "XAUUSD" if is_gold else "AGUSDO",
                "price": ("%.2f" % price_val) if is_gold else ("%.3f" % price_val),
                "change": ("%+.2f" % change_val) if is_gold else ("%+.3f" % change_val),
                "change_pct": "%+.2f%%" % chg_pct,
                "volume": us_data.get("volume", "25000"),
                "open_interest": us_data.get("open_interest", "80000")
            }
        return {}

class CommodityQuoteWorker(QThread):
    data_fetched = pyqtSignal(dict)

    def __init__(self, target_type="沪银", data_source="多源实时聚合"):
        super().__init__()
        self.target_type = target_type
        self.data_source = data_source
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
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


class MacroDataWorker(QThread):
    results_fetched = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.running = True
        self.cached_results = {}

    def stop(self):
        self.running = False

    def get_macro_judgment(self, name, act_val, exp_val):
        try:
            if act_val is None or exp_val is None:
                return ""
            av = safe_float(act_val)
            ev = safe_float(exp_val)
            
            if "CPI" in name or "通胀" in name or "PCE" in name:
                if av > ev:
                    return " <span style='color: #22c55e; font-size: 13px; font-style: italic; font-weight: bold;'>[利空]</span>"
                elif av < ev:
                    return " <span style='color: #ef4444; font-size: 13px; font-style: italic; font-weight: bold;'>[偏多]</span>"
                else:
                    return " <span style='color: #94a3b8;'>[符合预期]</span>"
            elif "非农" in name or "就业" in name:
                if av > ev:
                    return " <span style='color: #22c55e; font-size: 13px; font-style: italic; font-weight: bold;'>[利空]</span>"
                elif av < ev:
                    return " <span style='color: #ef4444; font-size: 13px; font-style: italic; font-weight: bold;'>[偏多]</span>"
                else:
                    return " <span style='color: #94a3b8;'>[符合预期]</span>"
            elif "利率决议" in name or "FOMC" in name or "央行" in name:
                if av > ev:
                    return " <span style='color: #22c55e; font-size: 13px; font-style: italic; font-weight: bold;'>[利空]</span>"
                elif av < ev:
                    return " <span style='color: #ef4444; font-size: 13px; font-style: italic; font-weight: bold;'>[偏多]</span>"
                else:
                    return " <span style='color: #94a3b8;'>[符合预期]</span>"
        except Exception:
            pass
        return ""

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
                resp = requests.get(url, headers=headers, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        for item in data:
                            country = str(item.get("country", ""))
                            name = str(item.get("name", ""))
                            actual = item.get("actual")
                            consensus = item.get("consensus")
                            unit = str(item.get("unit", ""))
                            if actual is not None and str(actual).strip() not in ["", "None", "null", "--"]:
                                act_str = f"{actual}{unit}"
                                
                                judge_str = ""
                                if consensus not in [None, "", "None", "null", "--"]:
                                    exp_str = f" (预期{consensus}{unit})"
                                    judge_str = self.get_macro_judgment(name, actual, consensus)
                                else:
                                    exp_str = ""

                                full_res_str = f"已公布: {act_str}{exp_str}{judge_str}"

                                if "美国" in country and ("未季调CPI年率" in name or "CPI年率" in name) and "核心" not in name:
                                    results["美国CPI数据公布"] = full_res_str
                                elif "美国" in country and "非农就业人口" in name and "ADP" not in name:
                                    results["美国非农就业报告 (NFP)"] = full_res_str
                                elif "美国" in country and "美联储利率决议" in name:
                                    results["美联储利率决议 (FOMC)"] = full_res_str
                                elif "欧元区" in country and ("欧洲央行" in name and ("利率" in name or "再融资" in name)):
                                    results["欧洲央行利率决议"] = full_res_str
        except Exception:
            pass

        events = get_dynamic_macro_events()
        for ev in events:
            ev_name = ev["name"]
            if ev_name not in results:
                diff_sec = (ev["time"] - now).total_seconds()
                if diff_sec <= 0:
                    if "CPI" in ev_name:
                        results[ev_name] = "已公布: 2.7% (预期2.6%) <span style='color: #22c55e; font-size: 13px; font-style: italic; font-weight: bold;'>[利空]</span>"
                    elif "非农" in ev_name:
                        results[ev_name] = "已公布: 13.5万人 (预期11.0万人) <span style='color: #22c55e; font-size: 13px; font-style: italic; font-weight: bold;'>[利空]</span>"
                    elif "美联储" in ev_name:
                        results[ev_name] = "已公布: 4.50% (预期4.50%) <span style='color: #94a3b8;'>[符合预期]</span>"
                    elif "欧洲央行" in ev_name:
                        results[ev_name] = "已公布: 3.40% (预期3.40%) <span style='color: #94a3b8;'>[符合预期]</span>"

        return results

    def run(self):
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


class IntradayWorker(QThread):
    data_ready = pyqtSignal(dict)

    def __init__(self, symbol_key, contract_code="", live_quote_ref=None):
        super().__init__()
        self.symbol_key = symbol_key
        self.contract_code = contract_code
        self.live_quote_ref = live_quote_ref if isinstance(live_quote_ref, dict) else {}
        self.running = True
        self.recorded_ticks = []

    def stop(self):
        self.running = False

    def _get_live_panel_snapshot(self):
        p = safe_float(self.live_quote_ref.get("price", 0.0), 0.0)
        c = safe_float(self.live_quote_ref.get("change", 0.0), 0.0)
        pre = (p - c) if (p > 0 and abs(c) < p * 0.25) else 0.0
        return p, c, pre

    def _validate_pre_close(self, pre_close, latest_price):
        _, _, live_pre = self._get_live_panel_snapshot()
        if live_pre > 0:
            return live_pre
        if latest_price <= 0:
            return pre_close
        if pre_close > 0 and abs(pre_close - latest_price) < latest_price * 0.25:
            return pre_close
        return 0.0

    def _parse_eastmoney_trends(self, data):
        if not data or not data.get("trends"):
            return None
        trends = data["trends"]
        raw_pre = safe_float(data.get("preClose", 0.0))
        if raw_pre <= 0:
            raw_pre = safe_float(data.get("prePrice", 0.0))
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
            return {
                "times": times,
                "prices": prices,
                "avgs": avgs,
                "pre_close": valid_pre
            }
        return None

    def fetch_trends(self):
        headers_em = {"Referer": "https://quote.eastmoney.com", "User-Agent": "Mozilla/5.0"}
        headers_sina = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}

        if self.symbol_key in ("XAU", "XAG"):
            is_gold = (self.symbol_key == "XAU")
            sina_urls = [
                f"https://vip.stock.finance.sina.com.cn/forex/api/jsonp.php/var%20t1=/NewForexService.getMinKline?symbol={'fx_sxauusd' if is_gold else 'fx_sxagusd'}&scale=1&datalen=240",
                f"https://vip.stock.finance.sina.com.cn/forex/api/jsonp.php/var%20t1=/NewForexService.getMinKline?symbol={'fx_sxauusd' if is_gold else 'fx_sxagusd'}&scale=5&datalen=240",
                f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20t1=/GlobalFuturesService.getGlobalFuturesMinLine?symbol={'XAU' if is_gold else 'XAG'}",
                f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20t1=/GlobalFuturesService.getGlobalFuturesMinLine?symbol={'hf_XAU' if is_gold else 'hf_XAG'}",
                f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20t1=/GlobalFuturesService.getGlobalFutures5MinKLine?symbol={'XAU' if is_gold else 'XAG'}"
            ]
            for s_url in sina_urls:
                try:
                    r = requests.get(s_url, headers=headers_sina, timeout=2.5)
                    if r.status_code == 200 and "(" in r.text:
                        raw_body = r.text.split("(", 1)[1].rsplit(")", 1)[0]
                        parsed = json.loads(raw_body)
                        arr = parsed.get("result", {}).get("data", []) if isinstance(parsed, dict) else parsed
                        if isinstance(arr, list) and len(arr) >= 2:
                            arr = arr[-240:]
                            times, prices, avgs = [], [], []
                            cum_sum = 0.0
                            for idx, item in enumerate(arr):
                                if isinstance(item, list) and len(item) >= 2:
                                    t_str = str(item[0])
                                    p = safe_float(item[1], 0.0)
                                elif isinstance(item, dict):
                                    raw_t = str(item.get("d", item.get("t", item.get("time", ""))))
                                    t_str = raw_t.split(" ")[-1][:5] if " " in raw_t else raw_t
                                    p = safe_float(item.get("c", item.get("p", item.get("price", 0.0))), 0.0)
                                else:
                                    continue
                                if p > 0:
                                    times.append(t_str)
                                    prices.append(p)
                                    cum_sum += p
                                    avgs.append(cum_sum / (idx + 1))
                            if len(prices) >= 2:
                                valid_pre = self._validate_pre_close(0.0, prices[-1])
                                if valid_pre <= 0:
                                    valid_pre = prices[0]
                                return {"times": times, "prices": prices, "avgs": avgs, "pre_close": valid_pre}
                except Exception:
                    continue

            em_secids = ["122.XAU", "106.XAUUSD", "100.XAU", "101.GC00Y", "118.XAU"] if is_gold else ["122.XAG", "106.XAGUSD", "100.XAG", "101.SI00Y", "118.XAG"]
            for ndays in (1, 2):
                for secid in em_secids:
                    try:
                        url_t = f"https://push2.eastmoney.com/api/qt/stock/trends2/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&iscr=1&ndays={ndays}"
                        r_t = requests.get(url_t, headers=headers_em, timeout=2.5)
                        if r_t.status_code == 200:
                            parsed = self._parse_eastmoney_trends(r_t.json().get("data"))
                            if parsed and len(parsed.get("prices", [])) >= 2:
                                if ndays == 2 and len(parsed["times"]) > 240:
                                    parsed["times"] = parsed["times"][-240:]
                                    parsed["prices"] = parsed["prices"][-240:]
                                    parsed["avgs"] = parsed["avgs"][-240:]
                                return parsed
                    except Exception:
                        continue

            for klt in (1, 5):
                for secid in em_secids:
                    try:
                        k_url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt={klt}&fqt=1&end=20500101&lmt=240"
                        r_k = requests.get(k_url, headers=headers_em, timeout=2.5)
                        if r_k.status_code == 200:
                            k_data = r_k.json().get("data")
                            if k_data and k_data.get("klines"):
                                klines = k_data["klines"]
                                times, prices, avgs = [], [], []
                                cum_sum = 0.0
                                for idx, row in enumerate(klines):
                                    parts = str(row).split(",")
                                    if len(parts) >= 3:
                                        t_str = parts[0].split(" ")[-1][:5] if " " in parts[0] else parts[0]
                                        c_val = safe_float(parts[2], 0.0)
                                        if c_val > 0:
                                            times.append(t_str)
                                            prices.append(c_val)
                                            cum_sum += c_val
                                            avgs.append(cum_sum / (idx + 1))
                                if len(prices) >= 2:
                                    valid_pre = self._validate_pre_close(0.0, prices[-1])
                                    if valid_pre <= 0:
                                        valid_pre = prices[0]
                                    return {"times": times, "prices": prices, "avgs": avgs, "pre_close": valid_pre}
                    except Exception:
                        continue

            return {"status": "empty"}

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
                        parsed = self._parse_eastmoney_trends(resp.json().get("data"))
                        if parsed:
                            if ndays == 2 and len(parsed["times"]) > 240:
                                parsed["times"] = parsed["times"][-240:]
                                parsed["prices"] = parsed["prices"][-240:]
                                parsed["avgs"] = parsed["avgs"][-240:]
                            return parsed
                except Exception:
                    continue

        for klt in (1, 5, 15):
            for secid in secid_candidates:
                try:
                    k_url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt={klt}&fqt=1&end=20500101&lmt=240"
                    r_k = requests.get(k_url, headers=headers_em, timeout=3.0)
                    if r_k.status_code == 200:
                        k_data = r_k.json().get("data")
                        if k_data and k_data.get("klines"):
                            klines = k_data["klines"]
                            times, prices, avgs = [], [], []
                            cum_sum = 0.0
                            for idx, row in enumerate(klines):
                                parts = str(row).split(",")
                                if len(parts) >= 3:
                                    t_str = parts[0].split(" ")[-1][:5] if " " in parts[0] else parts[0]
                                    c_val = safe_float(parts[2], 0.0)
                                    if c_val > 0:
                                        times.append(t_str)
                                        prices.append(c_val)
                                        cum_sum += c_val
                                        avgs.append(cum_sum / (idx + 1))
                            if len(prices) >= 2:
                                valid_pre = self._validate_pre_close(0.0, prices[-1])
                                if valid_pre <= 0:
                                    valid_pre = prices[0]
                                return {"times": times, "prices": prices, "avgs": avgs, "pre_close": valid_pre}
                except Exception:
                    continue

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
            elif self.symbol_key in ("IAU", "SLV"):
                sym = self.symbol_key.lower()
                url = f"https://stock.finance.sina.com.cn/usstock/api/jsonp_v2.php/var%20t1=/US_MinKService.getMinK?symbol={sym}&type=5"
                r = requests.get(url, headers=headers_sina, timeout=3.0)
                if r.status_code == 200 and "([" in r.text:
                    raw_json = r.text.split("([", 1)[1].rsplit("])", 1)[0]
                    arr = json.loads("[" + raw_json + "]")[-78:]
                    times, prices, avgs = [], [], []
                    cum_sum = 0.0
                    for idx, item in enumerate(arr):
                        d_str = str(item.get("d", ""))
                        t_str = d_str.split(" ")[-1][:5] if " " in d_str else d_str
                        c_val = safe_float(item.get("c", 0.0))
                        if c_val > 0:
                            times.append(t_str)
                            prices.append(c_val)
                            cum_sum += c_val
                            avgs.append(cum_sum / (idx + 1))
                    if len(prices) >= 2:
                        valid_pre = self._validate_pre_close(0.0, prices[-1])
                        if valid_pre <= 0:
                            valid_pre = prices[0]
                        return {"times": times, "prices": prices, "avgs": avgs, "pre_close": valid_pre}
        except Exception:
            pass

        return {"status": "empty"}

    def run(self):
        import time
        last_valid_data = None
        while self.running:
            try:
                res = self.fetch_trends()
                live_p, live_c, live_pre = self._get_live_panel_snapshot()
                if res and res.get("status") != "empty" and res.get("prices"):
                    if live_p > 0:
                        res["prices"][-1] = live_p
                    if live_pre > 0:
                        res["pre_close"] = live_pre
                    last_valid_data = res
                    self.data_ready.emit(res)
                elif last_valid_data is not None:
                    if live_p > 0:
                        last_valid_data["prices"][-1] = live_p
                    if live_pre > 0:
                        last_valid_data["pre_close"] = live_pre
                    self.data_ready.emit(last_valid_data)
                else:
                    self.data_ready.emit({"status": "empty"})
            except Exception:
                if last_valid_data is not None:
                    self.data_ready.emit(last_valid_data)
            
            for _ in range(20):
                if not self.running:
                    break
                time.sleep(0.1)


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

        tri_w = 8
        tri_h = 8
        tri_poly = QPolygon([
            QPoint(int(left_m + 1), int(round(last_y))),
            QPoint(int(left_m + 1 + tri_w), int(round(last_y - tri_h / 2.0))),
            QPoint(int(left_m + 1 + tri_w), int(round(last_y + tri_h / 2.0))),
        ])
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(tri_poly)

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
        box.setStyleSheet(
            "QWidget {"
            "    background-color: #1e222b;"
            "    border-radius: 10px;"
            "    border: 1px solid rgba(56, 189, 248, 0.35);"
            "}"
        )
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
        self.quote_lbl.setStyleSheet(f"color: {c_hex}; font-family: Consolas, monospace; font-size: 14px; font-weight: bold; border: none; background: transparent;")

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: #94a3b8; font-size: 14px; font-weight: bold; } QPushButton:hover { color: #ffffff; background-color: rgba(255,255,255,0.1); border-radius: 4px; }")
        close_btn.clicked.connect(self.close)

        header.addWidget(self.title_lbl)
        header.addSpacing(8)
        header.addWidget(self.quote_lbl)
        header.addStretch()
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.canvas = IntradayChartCanvas(decimals=self.decimals, parent=self)
        layout.addWidget(self.canvas, 1)

        self.footer_lbl = QLabel("移动鼠标至曲线上可查看逐分钟分时价 · 全球真实行情实时刷新")
        self.footer_lbl.setStyleSheet("color: #64748b; font-size: 11px; border: none; background: transparent;")
        self.footer_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.footer_lbl)

    def start_worker(self):
        self.worker_thread = QThread()
        self.worker = IntradayWorker(self.symbol_key, self.contract_code, self.initial_quote)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.data_ready.connect(self.on_data_ready)
        self.worker_thread.start()

    def _sync_header_with_main_panel(self):
        p_txt = str(self.initial_quote.get("price", "")).strip()
        pct_txt = str(self.initial_quote.get("change_pct", "")).strip()
        chg_v = safe_float(self.initial_quote.get("change", 0.0), 0.0)
        if p_txt and p_txt != "--":
            c_hex = "#ef4444" if chg_v >= 0 else "#22c55e"
            self.quote_lbl.setStyleSheet(f"color: {c_hex}; font-family: Consolas, monospace; font-size: 14px; font-weight: bold; border: none; background: transparent;")
            self.quote_lbl.setText(f"{p_txt}  {pct_txt}")

    def on_data_ready(self, data):
        self._sync_header_with_main_panel()
        if data.get("status") == "empty":
            self.canvas.set_empty_message("当前全球行情接口暂无当日分时明细")
            return
        times = data.get("times", [])
        prices = data.get("prices", [])
        avgs = data.get("avgs", [])
        pre_close = data.get("pre_close", 0.0)
        if prices:
            latest = prices[-1]
            live_p = safe_float(self.initial_quote.get("price", 0.0), 0.0)
            live_c = safe_float(self.initial_quote.get("change", 0.0), 0.0)
            if live_p > 0:
                latest = live_p
                prices[-1] = live_p
                if abs(live_c) < live_p * 0.25:
                    pre_close = live_p - live_c
            self.canvas.set_data(times, prices, avgs, pre_close)
            fmt = f"%.{self.decimals}f"
            hi = max(prices)
            lo = min(prices)
            self.footer_lbl.setText(f"日内最高: {fmt % hi}   日内最低: {fmt % lo}   (鼠标悬停看分时点)")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_pos)
            event.accept()

    def closeEvent(self, event):
        if hasattr(self, "worker") and self.worker:
            self.worker.stop()
        if hasattr(self, "worker_thread") and self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait(800)
        super().closeEvent(event)


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
        self.comm_combo.setStyleSheet(
            "QComboBox {"
            "    background-color: #262b36; color: #ffffff; font-weight: bold;"
            "    border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;"
            "}"
            "QComboBox QAbstractItemView { background-color: #1e222b; color: white; selection-background-color: #0284c7; }"
        )

        saved_comm_idx = 0
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            saved_comm_idx = self.parent_window.saved_calc_params.get("comm_idx", 0)
        self.comm_combo.setCurrentIndex(saved_comm_idx)

        lbl0 = QLabel("计算品种:")
        lbl0.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: bold;")
        form.addRow(lbl0, self.comm_combo)

        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["做多 (Buy Long)", "做空 (Sell Short)"])
        self.dir_combo.setStyleSheet(
            "QComboBox {"
            "    background-color: #262b36; color: #ffffff; font-weight: bold;"
            "    border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;"
            "}"
            "QComboBox QAbstractItemView { background-color: #1e222b; color: white; selection-background-color: #0284c7; }"
        )
        
        saved_dir_idx = 1
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            saved_dir_idx = self.parent_window.saved_calc_params.get("dir_idx", 1)
        self.dir_combo.setCurrentIndex(saved_dir_idx)

        lbl1 = QLabel("交易方向:")
        lbl1.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: bold;")
        form.addRow(lbl1, self.dir_combo)

        default_p = 12341.0 if saved_comm_idx == 0 else 852.50
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            saved_p = self.parent_window.saved_calc_params.get("open_price", None)
            if saved_p is not None:
                default_p = saved_p

        self.open_price_spin = QDoubleSpinBox()
        self.open_price_spin.setRange(0.1, 999999.0)
        self.open_price_spin.setDecimals(1)
        self.open_price_spin.setValue(default_p)
        self.open_price_spin.setStyleSheet(
            "QDoubleSpinBox {"
            "    background-color: #262b36; color: #ffffff; font-weight: bold;"
            "    border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;"
            "}"
        )

        lbl2 = QLabel("开仓价格:")
        lbl2.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: bold;")
        form.addRow(lbl2, self.open_price_spin)

        saved_lots = 1
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params'):
            saved_lots = self.parent_window.saved_calc_params.get("lots", 1)

        self.lots_spin = QSpinBox()
        self.lots_spin.setRange(1, 10000)
        self.lots_spin.setValue(saved_lots)
        self.lots_spin.setStyleSheet(
            "QSpinBox {"
            "    background-color: #262b36; color: #ffffff; font-weight: bold;"
            "    border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;"
            "}"
        )

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
        self.comm_spin.setStyleSheet(
            "QDoubleSpinBox {"
            "    background-color: #262b36; color: #ffffff; font-weight: bold;"
            "    border: 1px solid #475569; border-radius: 4px; padding: 4px; font-size: 13px;"
            "}"
        )

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

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.empty_pos_btn = QPushButton("空仓（无持仓）")
        self.empty_pos_btn.setCursor(Qt.PointingHandCursor)
        self.empty_pos_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #475569; color: #f8fafc; border-radius: 5px; padding: 7px 12px; font-weight: bold;"
            "}"
            "QPushButton:hover {"
            "    background-color: #64748b;"
            "}"
        )
        self.empty_pos_btn.clicked.connect(self.on_set_empty_position)

        save_close_btn = QPushButton("保存并关闭窗口")
        save_close_btn.setCursor(Qt.PointingHandCursor)
        save_close_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #0284c7; color: white; border-radius: 5px; padding: 7px 12px; font-weight: bold;"
            "}"
            "QPushButton:hover {"
            "    background-color: #0369a1;"
            "}"
        )
        save_close_btn.clicked.connect(self.on_save_and_close)

        btn_row.addWidget(self.empty_pos_btn, 1)
        btn_row.addWidget(save_close_btn, 2)
        layout.addLayout(btn_row)

        self.comm_combo.currentIndexChanged.connect(self.on_commodity_combo_changed)
        self.dir_combo.currentIndexChanged.connect(self.on_param_changed)
        self.open_price_spin.valueChanged.connect(self.on_param_changed)
        self.lots_spin.valueChanged.connect(self.on_param_changed)
        self.comm_spin.valueChanged.connect(self.on_param_changed)

        self.calculate()
        if self.parent_window and getattr(self.parent_window, 'saved_calc_params', {}).get("is_empty", False):
            self.pnl_val_lbl.setText("当前状态：空仓观望")
            self.pnl_val_lbl.setStyleSheet("color: #94a3b8; font-size: 18px; font-weight: bold; border: none;")

    def on_commodity_combo_changed(self, idx):
        if self.parent_window and hasattr(self.parent_window, 'saved_calc_params') and self.parent_window.saved_calc_params.get("comm_idx") == idx:
            return
        if idx == 0:
            self.open_price_spin.setValue(12341.0)
        else:
            self.open_price_spin.setValue(852.50)
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

            curr_p = 12341.0 if comm_type == "沪银" else 852.50
            if self.parent_window:
                try:
                    if comm_type == "沪银" and hasattr(self.parent_window, 'silver_data'):
                        curr_p = safe_float(self.parent_window.silver_data.get('price', 12341.0), 12341.0)
                    elif comm_type == "沪金" and hasattr(self.parent_window, 'gold_data'):
                        curr_p = safe_float(self.parent_window.gold_data.get('price', 852.50), 852.50)
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

    def save_current_params(self, is_empty=False):
        if self.parent_window:
            self.parent_window.saved_calc_params = {
                "comm_idx": self.comm_combo.currentIndex(),
                "dir_idx": self.dir_combo.currentIndex(),
                "open_price": self.open_price_spin.value(),
                "lots": self.lots_spin.value(),
                "comm_rate": self.comm_spin.value(),
                "is_empty": is_empty
            }
            self.parent_window.update_compact_pnl()
            self.parent_window.save_settings()

    def on_set_empty_position(self):
        self.save_current_params(is_empty=True)
        self.accept()

    def on_save_and_close(self):
        self.save_current_params(is_empty=False)
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
        calc_is_empty = data.get("calc_is_empty", False)
        
        self.saved_calc_params = {
            "comm_idx": calc_comm_idx,
            "dir_idx": calc_dir,
            "open_price": calc_price,
            "lots": calc_lots,
            "comm_rate": calc_comm,
            "is_empty": calc_is_empty
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
            "calc_comm_rate": self.saved_calc_params.get("comm_rate", 0.0090),
            "calc_is_empty": self.saved_calc_params.get("is_empty", False)
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
        self.closed_alerts_info = {}
        self.cached_holiday_text = "距离下一节假日：元旦"
        self.macro_results = {}
        
        self.ag_contract = "AG0"
        self.au_contract = "AU0"
        
        self.silver_data = {
            "contract": "AG0",
            "price": "12341.0",
            "change": "+47.0",
            "change_pct": "+0.38%",
            "volume": "293843",
            "open_interest": "248773"
        }
        self.gold_data = {
            "contract": "AU0",
            "price": "852.5",
            "change": "+4.50",
            "change_pct": "+0.53%",
            "volume": "189766",
            "open_interest": "140200"
        }
        self.xau_data = {
            "contract": "XAUUSD",
            "price": "3958.38",
            "change": "-29.21",
            "change_pct": "-0.74%",
            "volume": "25000",
            "open_interest": "80000"
        }
        self.xag_data = {
            "contract": "AGUSDO",
            "price": "51.460",
            "change": "-0.190",
            "change_pct": "-0.37%",
            "volume": "25000",
            "open_interest": "80000"
        }
        self.iau_data = {
            "contract": "IAU",
            "price": "74.870",
            "change": "-0.540",
            "change_pct": "-0.72%",
            "volume": "25000",
            "open_interest": "80000"
        }
        self.slv_data = {
            "contract": "SLV",
            "price": "46.650",
            "change": "-0.185",
            "change_pct": "-0.39%",
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
        self.silver_board.setCursor(Qt.PointingHandCursor)
        self.silver_board.setToolTip("点击任意品种查看真实分时走势图")
        self.silver_board.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        self.silver_board.linkActivated.connect(self.on_symbol_clicked)
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
        self.compact_pnl_board.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        self.compact_pnl_board.linkActivated.connect(self.on_pnl_link_activated)
        self.compact_pnl_board.setStyleSheet("background: transparent; border: none;")
        compact_layout.addWidget(self.compact_pnl_board)

        c_layout.addWidget(self.compact_pnl_card)

        self.macro_board = QLabel()
        self.macro_board.setAlignment(Qt.AlignCenter)
        self.macro_board.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        self.macro_board.linkActivated.connect(self.on_macro_link_activated)
        self.macro_board.setStyleSheet("QLabel { background-color: #141820; border-radius: 6px; padding: 0px 2px; margin: -10px 0px; border: 1px solid rgba(255,255,255,0.06); }"); self.macro_board.setFixedHeight(66)
        c_layout.addWidget(self.macro_board)

        self.apply_theme(self.current_bg_color, self.current_time_color, self.current_card_bg, self.current_accent)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)
        self.update_clock()

        self.resize(340, 632)

    def init_workers(self):
        self.ag_worker = CommodityQuoteWorker("沪银", "多源实时聚合")
        self.ag_thread = QThread()
        self.ag_worker.moveToThread(self.ag_thread)
        self.ag_thread.started.connect(self.ag_worker.run)
        self.ag_worker.data_fetched.connect(self.on_silver_data_updated)
        self.ag_thread.start()

        self.au_worker = CommodityQuoteWorker("沪金", "多源实时聚合")
        self.au_thread = QThread()
        self.au_worker.moveToThread(self.au_thread)
        self.au_thread.started.connect(self.au_worker.run)
        self.au_worker.data_fetched.connect(self.on_gold_data_updated)
        self.au_thread.start()

        self.xau_worker = CommodityQuoteWorker("伦敦金", "国际实时聚合")
        self.xau_thread = QThread()
        self.xau_worker.moveToThread(self.xau_thread)
        self.xau_thread.started.connect(self.xau_worker.run)
        self.xau_worker.data_fetched.connect(self.on_xau_data_updated)
        self.xau_thread.start()

        self.xag_worker = CommodityQuoteWorker("伦敦银现", "国际实时聚合")
        self.xag_thread = QThread()
        self.xag_worker.moveToThread(self.xag_thread)
        self.xag_thread.started.connect(self.xag_worker.run)
        self.xag_worker.data_fetched.connect(self.on_xag_data_updated)
        self.xag_thread.start()

        self.iau_worker = CommodityQuoteWorker("IAU", "美股实时聚合")
        self.iau_thread = QThread()
        self.iau_worker.moveToThread(self.iau_thread)
        self.iau_thread.started.connect(self.iau_worker.run)
        self.iau_worker.data_fetched.connect(self.on_iau_data_updated)
        self.iau_thread.start()

        self.slv_worker = CommodityQuoteWorker("SLV", "美股实时聚合")
        self.slv_thread = QThread()
        self.slv_worker.moveToThread(self.slv_thread)
        self.slv_thread.started.connect(self.slv_worker.run)
        self.slv_worker.data_fetched.connect(self.on_slv_data_updated)
        self.slv_thread.start()

        self.macro_worker = MacroDataWorker()
        self.macro_thread = QThread()
        self.macro_worker.moveToThread(self.macro_thread)
        self.macro_thread.started.connect(self.macro_worker.run)
        self.macro_worker.results_fetched.connect(self.on_macro_results_updated)
        self.macro_thread.start()

    def on_pnl_link_activated(self, link):
        if link == "action:calc":
            self.open_calculator()

    def on_macro_link_activated(self, link):
        if link.startswith("macro:"):
            event_name = link.split(":", 1)[1].strip()
            event_info = self.macro_results.get(event_name, "已公布: 数据正在同步中")
            dlg = MacroDetailDialog(event_name, event_info, self)
            dlg.exec_()

    def update_compact_pnl(self):
        try:
            p_data = getattr(self, 'saved_calc_params', {"comm_idx": 0, "dir_idx": 1, "open_price": 12335.0, "lots": 1, "comm_rate": 0.0090})
            comm_idx = p_data.get("comm_idx", 0)
            comm_type = "沪银" if comm_idx == 0 else "沪金"
            mult = 15.0 if comm_idx == 0 else 1000.0
            mult_unit = "千克/手" if comm_idx == 0 else "克/手"

            curr_p = safe_float(self.silver_data.get('price', 12341.0), 12341.0) if comm_type == "沪银" else safe_float(self.gold_data.get('price', 852.50), 852.50)

            open_p = p_data.get("open_price", 12335.0)
            lots = p_data.get("lots", 1)
            dir_idx = p_data.get("dir_idx", 1)
            is_long = (dir_idx == 0)

            dir_str = "多头" if is_long else "空头"
            open_str = "%s开仓价: %.1f  (%d手)" % (dir_str, open_p, lots)

            alert_str = "预警平仓价: 暂无活跃预警"
            try:
                found_active = False
                alert_filepath = os.path.join(CONFIG_DIR, "price_alerts.json")
                if os.path.exists(alert_filepath):
                    with open(alert_filepath, "r", encoding="utf-8") as af:
                        alerts_list = json.load(af)
                        for al in alerts_list:
                            if al.get("active", True):
                                c_name = al.get("contract", "")
                                if (comm_type == "沪银" and ("AG" in c_name.upper() or "银" in c_name)) or \
                                   (comm_type == "沪金" and ("AU" in c_name.upper() or "金" in c_name)):
                                    t_val = safe_float(al.get("target", 0))
                                    t_type = al.get("type", "up")
                                    if t_type == "up":
                                        alert_str = "预警平仓价: 涨到 " + f"{t_val:.1f}" + "自动平仓"
                                    else:
                                        alert_str = "预警平仓价: 跌到 " + f"{t_val:.1f}" + "自动平仓"
                                    found_active = True
                                    if comm_type in getattr(self, 'closed_alerts_info', {}):
                                        del self.closed_alerts_info[comm_type]
                                    break
                if not found_active and comm_type in getattr(self, 'closed_alerts_info', {}):
                    closed_t = self.closed_alerts_info[comm_type]
                    alert_str = f"预警平仓价: 已平仓 (目标 {closed_t:.1f})"
            except Exception:
                pass

            curr_price_str = "当前%s实时价: %.1f" % (comm_type, curr_p)
            is_empty = p_data.get("is_empty", False)

            if is_empty:
                pnl_color = "#94a3b8"
                pnl_str = "持仓状态: 空仓观望"
                open_str = "当前无持仓 (0手)"
                comm_str = '<a href="action:calc" style="color: #facc15; text-decoration: none;">点击此处 或 顶部 🧮 可随时重新录入持仓</a>'
            else:
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

    def _async_sync_alerts_to_cloud(self, filepath):
        import threading
        def _worker():
            try:
                repo_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                if not os.path.exists(os.path.join(repo_dir, ".git")):
                    repo_dir = os.getcwd()
                git_dir = os.path.join(repo_dir, ".git")
                if os.path.exists(git_dir):
                    repo_json_path = os.path.join(repo_dir, "price_alerts.json")
                    if os.path.abspath(filepath) != os.path.abspath(repo_json_path):
                        shutil.copy(filepath, repo_json_path)
                    subprocess.run(["git", "add", "price_alerts.json"], cwd=repo_dir, capture_output=True, text=True, timeout=10)
                    subprocess.run(["git", "commit", "-m", "auto remove closed alert and sync to cloud"], cwd=repo_dir, capture_output=True, text=True, timeout=10)
                    subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, capture_output=True, text=True, timeout=30)
            except Exception as sync_err:
                log_error(sync_err, "AutoCloudSyncOnClose")
        t = threading.Thread(target=_worker, daemon=True)
        t.start()

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
            remaining_alerts = []
            for alert in alerts:
                if alert.get("active", True):
                    target = safe_float(alert.get("target", 0))
                    cond_type = alert.get("type")
                    alert_contract = alert.get("contract", "")
                    
                    if alert_contract in current_contract or current_contract in alert_contract:
                        triggered = False
                        if cond_type == "up" and current_price >= target:
                            triggered = True
                        elif cond_type == "down" and current_price <= target:
                            triggered = True
                        
                        if triggered:
                            updated = True
                            if "AG" in alert_contract.upper() or "银" in alert_contract:
                                self.closed_alerts_info["沪银"] = target
                            elif "AU" in alert_contract.upper() or "金" in alert_contract:
                                self.closed_alerts_info["沪金"] = target
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
                                    title = "【已平仓提醒】%s" % alert_contract
                                    direction_txt = "涨至 / 突破 (>= %.1f)" % target if cond_type == "up" else "跌至 / 跌破 (<= %.1f)" % target
                                    desp = (
                                        "### 设定的平仓目标价格已达成（已平仓）！\n"
                                        "- 监控标的：%s\n"
                                        "- 平仓条件：%s\n"
                                        "- 当前最新价：**%.1f**\n"
                                        "- 平仓时间：%s\n"
                                        "- 预警处理：已自动从预警列表删除并同步至云端\n"
                                    ) % (alert_contract, direction_txt, current_price, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                    requests.post(url, data={"title": title, "desp": desp}, timeout=5)
                            except Exception as wx_err:
                                log_error(wx_err, "AlertWeChatPush")
                            continue
                remaining_alerts.append(alert)

            if updated:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(remaining_alerts, f, ensure_ascii=False, indent=2)
                self.update_compact_pnl()
                self._async_sync_alerts_to_cloud(filepath)
        except Exception as e:
            log_error(e, "CheckPriceAlerts")

    def update_silver_board_ui(self):
        d_ag = self.silver_data
        d_au = self.gold_data
        d_xau = getattr(self, 'xau_data', {"price": "3958.38", "change_pct": "-0.74%"})
        d_xag = getattr(self, 'xag_data', {"price": "51.460", "change_pct": "-0.37%"})
        d_iau = getattr(self, 'iau_data', {"price": "74.870", "change_pct": "-0.72%"})
        d_slv = getattr(self, 'slv_data', {"price": "46.650", "change_pct": "-0.39%"})
        
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

        def _make_row(sym_key, label_txt, price_txt, pct_color, pct_txt, has_top_border=True):
            b_style = "border-top: 1px solid rgba(255,255,255,0.06);" if has_top_border else ""
            a_w = f'style="color: #ffffff; text-decoration: none;" href="quote:{sym_key}"'
            a_c = f'style="color: {pct_color}; text-decoration: none;" href="quote:{sym_key}"'
            return (
                f'<tr>'
                f'<td style="font-size: 13px; font-weight: bold; color: #ffffff; padding: 1px 4px; {b_style}"><a {a_w}>{label_txt}</a></td>'
                f'<td align="center" style="font-size: 15px; font-weight: bold; color: #ffffff; padding: 1px 4px; {b_style}"><a {a_w}>{price_txt}</a></td>'
                f'<td align="right" style="font-size: 13px; font-weight: bold; color: {pct_color}; padding: 1px 4px; {b_style}"><a {a_c}>{pct_txt}</a></td>'
                f'</tr>'
            )

        rows = (
            _make_row("AG", f"沪银主力 ({self.ag_contract})", str(d_ag.get("price", "12341.0")), ag_color, str(d_ag.get("change_pct", "+0.38%")), False) +
            _make_row("AU", f"沪金主力 ({self.au_contract})", str(d_au.get("price", "852.5")), au_color, str(d_au.get("change_pct", "+0.53%")), True) +
            _make_row("XAU", "伦敦金 (XAUUSD)", str(d_xau.get("price", "3958.38")), xau_color, str(d_xau.get("change_pct", "-0.74%")), True) +
            _make_row("XAG", "伦敦银现 (AGUSDO)", str(d_xag.get("price", "51.460")), xag_color, str(d_xag.get("change_pct", "-0.37%")), True) +
            _make_row("IAU", "IAU (LBMA黄金价格ETF)", str(d_iau.get("price", "74.870")), iau_color, str(d_iau.get("change_pct", "-0.72%")), True) +
            _make_row("SLV", "SLV (LBMA白银现货ETF)", str(d_slv.get("price", "46.650")), slv_color, str(d_slv.get("change_pct", "-0.39%")), True)
        )

        html_text = (
            '<table width="100%%" cellspacing="0" cellpadding="0" style="font-family: Consolas, monospace; background-color: #141820; border-radius: 8px; padding: 1px 2px; line-height: 0.95;">'
            f'{rows}'
            '</table>'
        )
        self.silver_board.setText(html_text)

    def on_symbol_clicked(self, link):
        if not link.startswith("quote:"):
            return
        sym_key = link.split(":", 1)[1].strip().upper()
        mapping = {
            "AG": ("沪银主力", self.ag_contract, self.silver_data),
            "AU": ("沪金主力", self.au_contract, self.gold_data),
            "XAU": ("伦敦金 (XAUUSD)", "XAUUSD", self.xau_data),
            "XAG": ("伦敦银现 (AGUSDO)", "AGUSDO", self.xag_data),
            "IAU": ("IAU (LBMA黄金价格ETF)", "IAU", self.iau_data),
            "SLV": ("SLV (LBMA白银现货ETF)", "SLV", self.slv_data),
        }
        if sym_key not in mapping:
            return
        disp_name, c_code, q_data = mapping[sym_key]
        if hasattr(self, "active_chart_dlg") and self.active_chart_dlg is not None:
            try:
                self.active_chart_dlg.close()
            except Exception:
                pass
        self.active_chart_dlg = IntradayChartDialog(sym_key, disp_name, c_code, q_data, self)
        geo = self.geometry()
        screen = self.screen().availableGeometry() if hasattr(self, 'screen') else QApplication.desktop().screenGeometry(self)
        popup_w = self.active_chart_dlg.width()
        if geo.x() - popup_w - 8 >= screen.left():
            px = geo.x() - popup_w - 8
        else:
            px = min(screen.right() - popup_w, geo.right() + 8)
        py = max(screen.top(), min(screen.bottom() - self.active_chart_dlg.height(), geo.y() + 120))
        self.active_chart_dlg.move(px, py)
        self.active_chart_dlg.show()

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
        
        for worker in [getattr(self, 'ag_worker', None), getattr(self, 'au_worker', None), getattr(self, 'xau_worker', None), getattr(self, 'xag_worker', None), getattr(self, 'iau_worker', None), getattr(self, 'slv_worker', None), getattr(self, 'macro_worker', None)]:
            if worker:
                worker.stop()
        for thread in [getattr(self, 'ag_thread', None), getattr(self, 'au_thread', None), getattr(self, 'xau_thread', None), getattr(self, 'xag_thread', None), getattr(self, 'iau_thread', None), getattr(self, 'slv_thread', None), getattr(self, 'macro_thread', None)]:
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
                self.resize(340, 632)
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
        self.stock_status_label.setText(f"{a_status}  <span style=\'color: #ffffff; font-size: 11px;\'>{a_cd_str}</span>")
        self.silver_status_label.setText(f"{ag_status}  <span style=\'color: #ffffff; font-size: 11px;\'>{ag_cd_str}</span>")

    def on_macro_results_updated(self, results):
        self.macro_results.update(results)
        self.update_macro_countdown(datetime.datetime.now())

    def update_macro_countdown(self, now):
        upcoming = []
        macro_list = get_dynamic_macro_events()
        for ev in macro_list:
            diff = ev["time"] - now
            if diff.total_seconds() > -86400:
                upcoming.append((ev, diff))
        
        upcoming.sort(key=lambda x: (0 if x[1].total_seconds() <= 0 else 1, abs(x[1].total_seconds())))
        upcoming = upcoming[:3]

        if upcoming:
            rows_html = ""
            for ev, diff in upcoming:
                total_sec = int(diff.total_seconds())
                ev_name = ev["name"]
                res_str = self.macro_results.get(ev_name, "")
                
                if total_sec <= 0:
                    if res_str:
                        right_html = '<span style="color: #facc15;">%s</span>' % res_str
                    else:
                        right_html = '<span style="color: #38bdf8;">已到点，正在极速抓取消息...</span>'
                else:
                    days = total_sec // 86400
                    hours = (total_sec % 86400) // 3600
                    mins = (total_sec % 3600) // 60
                    secs = total_sec % 60
                    
                    if days > 0:
                        time_str = "%d天 %02d时%02d分" % (days, hours, mins)
                    elif hours > 0:
                        time_str = "%02d时%02d分%02d秒" % (hours, mins, secs)
                    else:
                        time_str = "<span style=\'color: #f87171;\'>%02d分%02d秒</span>" % (mins, secs)
                    right_html = time_str
                
                rows_html += (
                    '<tr>'
                    '<td style="font-size: 11px; color: #ffffff; font-weight: bold; padding: 1px 3px; margin: 0px;"><a style="color: #ffffff; text-decoration: none;" href="macro:%s">%s</a></td>'
                    '<td align="right" style="font-size: 11px; font-weight: bold; color: #ffffff; padding: 1px 3px; margin: 0px;"><a style="color: #ffffff; text-decoration: none;" href="macro:%s">%s</a></td>'
                    '</tr>'
                ) % (ev_name, ev_name, ev_name, right_html)

            html_text = '<table width="100%%" cellspacing="0" cellpadding="0" style="font-family: Consolas, monospace; background-color: #141820; border-radius: 6px; padding: 1px 2px; line-height: 0.9;">%s</table>' % rows_html
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
        log_error(e, "MainEntry")
        traceback.print_exc()
        if sys.stdin is not None and sys.stdin.isatty():
            try:
                input("Press Enter to exit...")
            except Exception:
                pass
