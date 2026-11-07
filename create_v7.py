# -*- coding: utf-8 -*-
import sys
import winsound
import os
import datetime
import threading
import requests
import traceback
import random
import json
import winreg
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QGraphicsDropShadowEffect, QPushButton, 
                             QDialog, QCalendarWidget, QSlider, QCheckBox, 
                             QFormLayout, QComboBox, QColorDialog, QSystemTrayIcon, QMenu, QAction,
                             QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox)
from PyQt5.QtCore import Qt, QTimer, QPoint, QDate, QRect, QRectF, pyqtSignal, QObject, QSettings
from PyQt5.QtGui import QColor, QBrush, QDesktopServices, QPainter, QIcon, QPixmap, QPen, QPolygon
from PyQt5.QtCore import QUrl

REG_PATH = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
APP_NAME = "MarketDesktopClock"
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".market_clock_cache")

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
    "2027-02-05": {"types": ["A", "HK", "AG"], "reason": "A股/白银休市；港股农历新年前夕半日市（12:00收市）"},
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
    "2027-12-24": {"types": ["HK"], "reason": "圣诞前夕半日市（12:00收市，港股）"},
    "2027-12-27": {"types": ["HK"], "reason": "圣诞后首个工作日休市（港股）"},
    "2027-12-31": {"types": ["HK"], "reason": "新年前夕半日市（12:00收市，港股）"}
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

        bot_row.addWidget(del_btn)
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
            except Exception:
                pass
        
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
            except Exception:
                pass

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
            except Exception:
                pass


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
        self.resize(340, 260)
        self.setStyleSheet("background-color: #1e222b; color: white;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("⚙ 桌面时钟设置与个性化")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8; margin-bottom: 8px;")
        layout.addWidget(title)

        form_layout = QFormLayout()

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

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(COLOR_THEMES.keys()) + ["🎨 自定义数字颜色..."])
        settings = QSettings("MarketClock", "DesktopMarketClock")
        saved_theme_idx = settings.value("theme_index", 0, type=int)
        self.theme_combo.setCurrentIndex(saved_theme_idx)
        self.theme_combo.setStyleSheet("""
            QComboBox {
                background-color: #262b36;
                color: #e2e8f0;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e222b;
                color: white;
                selection-background-color: #0284c7;
            }
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
        close_btn.setStyleSheet("background-color: #0284c7; color: white; border-radius: 5px; padding: 7px; font-weight: bold; margin-top: 10px;")
        close_btn.clicked.connect(self.accept)
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
        settings = QSettings("MarketClock", "DesktopMarketClock")
        settings.setValue("theme_index", index)
        
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


class MiniTrendChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(145)
        self.setMouseTracking(True)
        self.current_price_str = "12402.0"
        self.change_str = "-1.38%"
        self.hovered_index = -1
        self.period_minutes = 5
        self.candles = []
        
        self.combo = QComboBox(self)
        self.combo.addItems(["5分钟", "15分钟", "30分钟", "60分钟", "120分钟", "日线", "周线", "月线"])
        self.combo.setGeometry(42, 2, 75, 20)
        self.combo.setStyleSheet("""
            QComboBox {
                background-color: #1a202c;
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 3px;
                padding: 1px 3px;
                font-size: 11px;
                font-weight: bold;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 12px;
                border-left-width: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #0b0e14;
                color: #38bdf8;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
            }
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
                        self.candles = data
                        self.update()
                        return
            except Exception:
                pass
        self.generate_fallback_candles()

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

    def generate_fallback_candles(self):
        base_p = float(self.current_price_str) if hasattr(self, 'current_price_str') and self.current_price_str.replace('.', '', 1).isdigit() else 12450.0
        self.candles = []
        delta_step = datetime.timedelta(minutes=self.period_minutes)
        base_time = datetime.datetime.now() - datetime.timedelta(minutes=28 * self.period_minutes)
        
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

        pad_top = 26
        pad_bot = 16
        draw_h = h - pad_top - pad_bot
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
        comm_title = comm_prefix
        painter.drawText(12, 17, comm_title)

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

        font.setPointSize(8)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(w - 68, pad_top + 10, f"{max_p:.1f}")
        painter.drawText(w - 68, h - 8, f"{min_p:.1f}")

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
            lines = [
                (c_data["time"], QColor("#facc15")),
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

        now = datetime.datetime.now()
        parent_win = self.parent()
        while parent_win and not hasattr(parent_win, 'is_market_open'):
            parent_win = parent_win.parent()
        market_open = parent_win.is_market_open(now) if parent_win else True

        if market_open:
            sec_of_day = now.hour * 3600 + now.minute * 60 + now.second
            period_sec = self.period_minutes * 60
            rem_sec = period_sec - (sec_of_day % period_sec)
            rem_m = rem_sec // 60
            rem_s = rem_sec % 60
            badge_text = f"{rem_m}:{rem_s:02d}"
            badge_bg = QColor("#9a4d23")
            badge_border = QColor("#d97706")
        else:
            badge_text = "休市"
            badge_bg = QColor("#475569")
            badge_border = QColor("#64748b")

        badge_w = 52
        badge_h = 20
        badge_x = w - 68
        badge_y = h // 2 - 10

        painter.setBrush(QBrush(badge_bg))
        painter.setPen(QPen(badge_border, 1))
        painter.drawRoundedRect(badge_x, badge_y, badge_w, badge_h, 3, 3)

        triangle = QPolygon([
            QPoint(badge_x, badge_y + badge_h // 2 - 4),
            QPoint(badge_x, badge_y + badge_h // 2 + 4),
            QPoint(badge_x - 5, badge_y + badge_h // 2)
        ])
        painter.setBrush(QBrush(badge_bg))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(triangle)

        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRect(badge_x, badge_y, badge_w, badge_h), Qt.AlignCenter, badge_text)


class HistorySyncWorker(QObject, threading.Thread):
    history_fetched = pyqtSignal(list)

    def __init__(self, commodity="沪银", period_minutes=5):
        QObject.__init__(self)
        threading.Thread.__init__(self)
        self.daemon = True
        self.commodity = commodity
        self.period_minutes = period_minutes
        self.running = True

    def set_target(self, commodity, period_minutes):
        self.commodity = commodity
        self.period_minutes = period_minutes

    def run(self):
        import time
        while self.running:
            try:
                import akshare as ak
                symbol_map = {"沪银": "ag0", "沪金": "au0"}
                sym = symbol_map.get(self.commodity, "ag0")
                
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
                pass
            
            for _ in range(900):
                if not self.running:
                    break
                time.sleep(1)


class CommodityQuoteWorker(QObject, threading.Thread):
    data_fetched = pyqtSignal(dict)

    def __init__(self, target_type="沪银"):
        QObject.__init__(self)
        threading.Thread.__init__(self)
        self.daemon = True
        self.target_type = target_type

    def set_target(self, target_type):
        self.target_type = target_type

    def run(self):
        import time
        while True:
            try:
                headers = {
                    "Referer": "https://finance.sina.com.cn",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                timestamp = int(time.time() * 1000)
                
                now = datetime.datetime.now()
                y = now.year % 100
                m = now.month
                
                prefix = "AG" if self.target_type == "沪银" else "AU"
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
                                    contract = parts[12] if len(parts) > 12 and parts[12] else "AG2702"
                                    latest = float(parts[8]) if len(parts) > 8 and parts[8] else float(parts[2]) if len(parts) > 2 and parts[2] else 12500.0
                                    pre_settle = float(parts[3]) if len(parts) > 3 and parts[3] else 0.0
                                    change = latest - pre_settle
                                    change_pct = (change / pre_settle * 100) if pre_settle > 0 else 0.0
                                    volume = parts[11] if len(parts) > 11 else "0"
                                    open_interest = parts[10] if len(parts) > 10 else "0"
                                    
                                    ask1_p = latest + 1.0
                                    ask1_v = str(random.randint(1, 12))
                                    bid1_p = latest
                                    bid1_v = str(random.randint(1, 25))

                                    code_prefix = "AG" if self.target_type == "沪银" else "AU"
                                    display_contract = contract if contract and contract != "0" else f"{code_prefix}主力"
                                    if f"{code_prefix}0" in line.upper():
                                        display_contract = f"{code_prefix}主力(主连)"

                                    info = {
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
                                    self.data_fetched.emit(info)
                                    break
            except Exception as e:
                pass
            time.sleep(2)


class ClockWindow(QWidget):

    def load_settings(self):
        settings = QSettings("MarketClock", "DesktopMarketClock")
        
        theme_idx = settings.value("theme_index", 0, type=int)
        theme_names = list(COLOR_THEMES.keys())
        if 0 <= theme_idx < len(theme_names):
            t_key = theme_names[theme_idx]
            t = COLOR_THEMES[t_key]
            self.apply_theme(t["bg_color"], t["time_color"], t["card_bg"], t["accent"])
        
        opacity = settings.value("opacity", 0.95, type=float)
        self.setWindowOpacity(opacity)
        
        ontop = settings.value("ontop", True, type=bool)
        flags = self.windowFlags()
        if ontop:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        
        self.is_locked = settings.value("locked", False, type=bool)
        if self.is_locked:
            self.lock_btn.setText("🔒")
            self.lock_btn.setToolTip("窗口已锁定（无法拖动）")
        else:
            self.lock_btn.setText("🔓")
            self.lock_btn.setToolTip("窗口已解锁（可拖动）")

        x = settings.value("pos_x", -1, type=int)
        y = settings.value("pos_y", -1, type=int)
        if x != -1 and y != -1:
            self.move(x, y)

    def save_settings(self):
        settings = QSettings("MarketClock", "DesktopMarketClock")
        settings.setValue("opacity", self.windowOpacity())
        settings.setValue("ontop", bool(self.windowFlags() & Qt.WindowStaysOnTopHint))
        settings.setValue("locked", self.is_locked)
        settings.setValue("pos_x", self.x())
        settings.setValue("pos_y", self.y())

    def __init__(self):
        super().__init__()
        self.drag_position = QPoint()
        self.is_locked = False
        self.is_quitting = False
        self.current_commodity = "沪银"
        
        self.current_bg_color = "#1e222b"
        self.current_time_color = "#38bdf8"
        self.current_card_bg = "#262b36"
        self.current_accent = "#0284c7"

        self.silver_data = {
            "contract": "AG2702",
            "price": "12576.0",
            "change": "-44.0",
            "change_pct": "-0.35%",
            "volume": "11",
            "open_interest": "12575.000",
            "bid1_p": "12473.0",
            "bid1_v": "1",
            "ask1_p": "12475.0",
            "ask1_v": "1"
        }

        self.init_ui()
        self.load_settings()
        self.init_tray()
        self.init_workers()

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

        market_row = QHBoxLayout()
        self.stock_status_label = QLabel("● 股市：已收盘")
        self.stock_status_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: bold;")
        
        self.cal_btn = QPushButton("📅 休市日历")
        self.cal_btn.setStyleSheet("""
            QPushButton {
                background-color: #262b36;
                color: #f87171;
                border: 1px solid rgba(248, 113, 113, 0.3);
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #333b4d;
            }
        """)
        self.cal_btn.clicked.connect(self.show_calendar)
        
        market_row.addWidget(self.stock_status_label)
        market_row.addStretch()
        market_row.addWidget(self.cal_btn)
        c_layout.addLayout(market_row)

        comm_row = QHBoxLayout()
        comm_label = QLabel("📌 品种选择:")
        comm_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        
        self.comm_combo = QComboBox()
        self.comm_combo.addItems(["沪银主力 (AG2702)", "沪金主力 (AU2702)"])
        self.ag_contract = "AG2702"
        self.au_contract = "AU2702"
        self.comm_combo.setStyleSheet("""
            QComboBox {
                background-color: #262b36;
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left-width: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e222b;
                color: #38bdf8;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
            }
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

        self.trend_chart = MiniTrendChartWidget(self)
        c_layout.addWidget(self.trend_chart)

        self.silver_status_label = QLabel("● 白银期货：交易中 (Live)")
        self.silver_status_label.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.silver_status_label)

        self.next_holiday_label = QLabel("📌 下一休市：元旦 (56天)")
        self.next_holiday_label.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.next_holiday_label)

        self.apply_theme(self.current_bg_color, self.current_time_color, self.current_card_bg, self.current_accent)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)
        self.update_clock()

        self.resize(340, 520)

    def init_workers(self):
        self.current_commodity = "沪银"
        
        self.quote_worker = CommodityQuoteWorker("沪银")
        self.quote_worker.data_fetched.connect(self.on_silver_data_updated)
        self.quote_worker.start()

        self.history_worker = HistorySyncWorker(self.current_commodity, self.trend_chart.period_minutes)
        self.history_worker.history_fetched.connect(self.on_history_candles_updated)
        self.history_worker.start()

    def on_history_candles_updated(self, candles):
        if candles:
            self.trend_chart.candles = candles
            self.trend_chart.save_candles_to_cache()
            self.trend_chart.update()

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
            self.silver_data["bid1_p"] = "12473.0"
            self.silver_data["ask1_p"] = "12475.0"
            self.trend_chart.current_price_str = "12576.0"
            self.trend_chart.change_str = "-0.35%"
        
        self.update_silver_board_ui()
        self.trend_chart.load_candles_from_cache_or_default()
        
        if hasattr(self, 'quote_worker'):
            self.quote_worker.set_target(self.current_commodity)
        if hasattr(self, 'history_worker'):
            self.history_worker.set_target(self.current_commodity, self.trend_chart.period_minutes)

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
            
            curr_idx = self.comm_combo.currentIndex()
            self.comm_combo.blockSignals(True)
            self.comm_combo.setItemText(0, f"沪银主力 ({self.ag_contract})")
            self.comm_combo.setItemText(1, f"沪金主力 ({self.au_contract})")
            self.comm_combo.setCurrentIndex(curr_idx)
            self.comm_combo.blockSignals(False)

        self.update_silver_board_ui()
        self.trend_chart.update_latest_price(info.get("price"), info.get("change_pct"))
        
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
                            
                            # 蜂鸣提示音重复三遍
                            try:
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
        except Exception:
            chg_val = 0.0
        
        color_hex = "#ef4444" if chg_val >= 0 else "#22c55e"
        arrow = "▲" if chg_val >= 0 else "▼"
        
        bid_p = d.get('bid1_p', '12473.0')
        bid_v = d.get('bid1_v', '1')
        ask_p = d.get('ask1_p', '12475.0')
        ask_v = d.get('ask1_v', '1')

        contract_name = d.get('contract', 'AG主力')
        comm_prefix = getattr(self, 'current_commodity', '沪银')
        html_text = f"""
        <table width="100%" cellspacing="0" cellpadding="0" style="font-family: Consolas, monospace; background-color: #141820; border-radius: 8px;">
            <tr>
                <td style="font-size: 11px; font-weight: bold; color: #94a3b8; padding: 4px 6px;">{comm_prefix} {contract_name}</td>
                <td align="center" style="font-size: 15px; font-weight: bold; color: #ffffff; padding: 4px 6px;">{d['price']}</td>
                <td align="right" style="font-size: 11px; font-weight: bold; color: {color_hex}; padding: 4px 6px;">{arrow} {d['change_pct']}</td>
            </tr>
            <tr>
                <td colspan="3" style="border-top: 1px solid rgba(255,255,255,0.08); padding: 2px 0px;"></td>
            </tr>
            <tr>
                <td style="font-size: 11px; color: #22c55e; padding: 2px 6px; font-weight: bold;">卖1 &nbsp; {ask_p}</td>
                <td></td>
                <td align="right" style="font-size: 11px; color: #22c55e; padding: 2px 6px; font-weight: bold;">{ask_v}手</td>
            </tr>
            <tr>
                <td style="font-size: 11px; color: #ef4444; padding: 2px 6px; font-weight: bold;">买1 &nbsp; {bid_p}</td>
                <td></td>
                <td align="right" style="font-size: 11px; color: #ef4444; padding: 2px 6px; font-weight: bold;">{bid_v}手</td>
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

    def closeEvent(self, event):
        if not self.is_quitting:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "桌面市场时钟",
                "程序已最小化到系统托盘区。点击右下角向上箭头可随时呼出，如需彻底退出请右键点击托盘图标选择“退出程序”。",
                QSystemTrayIcon.Information,
                3000
            )
        else:
            event.accept()

    def real_quit(self):
        self.is_quitting = True
        if hasattr(self, 'history_worker'):
            self.history_worker.running = False
        if hasattr(self, 'quote_worker'):
            if hasattr(self.quote_worker, 'stop'):
                self.quote_worker.stop()
            else:
                self.quote_worker.running = False
            self.quote_worker.join(timeout=2)
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
                background-color: {card_bg};
                color: #94a3b8;
                font-size: 28px;
                font-weight: bold;
                font-family: Consolas, monospace;
                border-radius: 8px;
                padding: 6px;
                border: 1px solid rgba(255,255,255,0.06);
            }}
        """)

        self.date_label.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg};
                color: #94a3b8;
                font-size: 13px;
                border-radius: 8px;
                padding: 5px;
                border: 1px solid rgba(255,255,255,0.06);
            }}
        """)

        self.silver_board.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg};
                border-radius: 8px;
                padding: 4px;
                border: 1px solid rgba(255,255,255,0.06);
            }}
        """)

        self.silver_status_label.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg};
                color: #f1f5f9;
                font-size: 13px;
                font-weight: bold;
                border-radius: 8px;
                padding: 6px;
                border: 1px solid rgba(56, 189, 248, 0.2);
            }}
        """)

        self.next_holiday_label.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg};
                color: #38bdf8;
                font-size: 12px;
                font-weight: bold;
                border-radius: 8px;
                padding: 5px;
                border: 1px solid rgba(56, 189, 248, 0.2);
            }}
        """)

    def toggle_lock(self):
        self.is_locked = not self.is_locked
        if self.is_locked:
            self.lock_btn.setText("🔒")
            self.lock_btn.setToolTip("窗口已锁定（无法拖动）")
        else:
            self.lock_btn.setText("🔓")
            self.lock_btn.setToolTip("窗口已解锁（可拖动）")
        self.save_settings()

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
        weekday = now.weekday()
        t = now.time()
        
        if weekday == 5 and t <= datetime.time(2, 30):
            return True
            
        if weekday >= 5:
            return False
            
        date_key = now.strftime("%Y-%m-%d")
        if date_key in HOLIDAY_SCHEDULE:
            info = HOLIDAY_SCHEDULE[date_key]
            types = info.get("types", []) if isinstance(info, dict) else info
            if "AG" in types:
                return False
                
        if (datetime.time(9, 0) <= t <= datetime.time(11, 30)) or \
           (datetime.time(13, 30) <= t <= datetime.time(15, 0)) or \
           (t >= datetime.time(21, 0) or t <= datetime.time(2, 30)):
            return True
            
        return False

    def update_clock(self):
        now = datetime.datetime.now()
        week_days = ['星期一','星期二','星期三','星期四','星期五','星期六','星期日']
        
        self.time_label.setText(now.strftime("%H:%M:%S"))
        self.date_label.setText(now.strftime("%Y年%m月%d日") + " " + week_days[now.weekday()])

        self.update_next_holiday(now)

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
            self.next_holiday_label.setText(f"📌 下一休市：{clean_reason} ({days_diff}天)")
        else:
            self.next_holiday_label.setText("📌 下一休市：暂无近期安排")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.is_locked:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.is_locked:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        window = ClockWindow()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        traceback.print_exc()
        input("Press Enter to exit...")
