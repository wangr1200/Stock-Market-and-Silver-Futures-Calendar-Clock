# -*- coding: utf-8 -*-
"""
Stock Market and Silver Futures Calendar Clock (桌面市场日历时钟)
完整功能升级版：实时接入行情 + 倒计时 + 托盘 + 主题配色
"""

import sys
import os
import datetime
import threading
import requests
import traceback
import winreg
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QGraphicsDropShadowEffect, QPushButton, 
                             QDialog, QCalendarWidget, QSlider, QCheckBox, 
                             QFormLayout, QComboBox, QColorDialog, QSystemTrayIcon, QMenu, QAction)
from PyQt5.QtCore import Qt, QTimer, QPoint, QDate, QRectF, pyqtSignal, QObject, QSettings
from PyQt5.QtGui import QColor, QBrush, QDesktopServices, QPainter, QIcon, QPixmap
from PyQt5.QtCore import QUrl

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
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
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

        title_lbl = QLabel(f"📌 {title_text}")
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
        self.setWindowTitle("2026-2027 股市及白银期货休市日历")
        self.resize(520, 440)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        title_label = QLabel("📅 2026–2027 年股市及白银期货休市安排看板")
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

        legend_label = QLabel("🔴 A股休市  |  🟣 港股休市  |  🔵 白银期货休市")
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
            if "AG" in types: type_desc.append("白银期货")
            
            types_str = "、".join(type_desc)
            msg_text = f"休市市场：{types_str}\n具体说明：{reason}"
            dlg = SilentTipDialog(f"休市提醒 ({date_str})", msg_text, self)
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


# 后台实时行情请求线程
class SilverQuoteWorker(QObject, threading.Thread):
    data_fetched = pyqtSignal(dict)

    def __init__(self):
        QObject.__init__(self)
        threading.Thread.__init__(self)
        self.daemon = True

    def run(self):
        import time
        while True:
            try:
                headers = {"Referer": "https://finance.sina.com.cn"}
                url = "https://hq.sinajs.cn/list=nf_ag2702"
                resp = requests.get(url, headers=headers, timeout=3)
                if resp.status_code == 200 and "hq_str_nf_ag2702" in resp.text:
                    data_str = resp.text.split('"')[1]
                    if data_str:
                        parts = data_str.split(',')
                        if len(parts) > 13:
                            contract = parts[12] if parts[12] else "AG2702"
                            latest = float(parts[8]) if parts[8] else float(parts[2])
                            pre_settle = float(parts[3]) if parts[3] else 0.0
                            change = latest - pre_settle
                            change_pct = (change / pre_settle * 100) if pre_settle > 0 else 0.0
                            volume = parts[11] if len(parts) > 11 else "0"
                            open_interest = parts[10] if len(parts) > 10 else "0"
                            
                            info = {
                                "contract": contract if contract else "AG2702",
                                "price": f"{latest:.1f}",
                                "change": f"{change:+.1f}",
                                "change_pct": f"{change_pct:+.2f}%",
                                "volume": volume,
                                "open_interest": open_interest
                            }
                            self.data_fetched.emit(info)
            except Exception:
                pass
            time.sleep(10)


class ClockWindow(QWidget):

    def load_settings(self):
        settings = QSettings("MarketClock", "DesktopMarketClock")
        
        # 1. 恢复主题
        theme_idx = settings.value("theme_index", 0, type=int)
        theme_names = list(COLOR_THEMES.keys())
        if 0 <= theme_idx < len(theme_names):
            t_key = theme_names[theme_idx]
            t = COLOR_THEMES[t_key]
            self.apply_theme(t["bg_color"], t["time_color"], t["card_bg"], t["accent"])
        
        # 2. 恢复透明度
        opacity = settings.value("opacity", 0.95, type=float)
        self.setWindowOpacity(opacity)
        
        # 3. 恢复置顶状态
        ontop = settings.value("ontop", True, type=bool)
        flags = self.windowFlags()
        if ontop:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        
        # 4. 恢复锁定状态
        self.is_locked = settings.value("locked", False, type=bool)
        if self.is_locked:
            self.lock_btn.setText("🔒")
            self.lock_btn.setToolTip("窗口已锁定（无法拖动）")
        else:
            self.lock_btn.setText("🔓")
            self.lock_btn.setToolTip("窗口已解锁（可拖动）")

        # 5. 恢复窗口位置
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
        
        self.current_bg_color = "#1e222b"
        self.current_time_color = "#38bdf8"
        self.current_card_bg = "#262b36"
        self.current_accent = "#0284c7"

        self.silver_data = {
            "contract": "AG2702",
            "price": "12402.0",
            "change": "-227.0",
            "change_pct": "-1.80%",
            "volume": "358210",
            "open_interest": "184920"
        }

        self.init_ui()
        self.load_settings()
        self.init_tray()
        self.init_quote_thread()

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
        c_layout.setSpacing(10)

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

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; font-size: 14px; color: #a1a1aa; }
            QPushButton:hover { color: #ffffff; background-color: rgba(255,255,255,0.1); border-radius: 4px; }
        """)
        self.settings_btn.setToolTip("打开高级设置与皮肤切换")
        self.settings_btn.clicked.connect(self.open_settings)

        top_bar.addWidget(self.lock_btn)
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

        self.weekday_label = QLabel("星期五")
        self.weekday_label.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.weekday_label)

        self.time_label = QLabel("19:04:57")
        self.time_label.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.time_label)

        self.date_label = QLabel("2026年11月06日")
        self.date_label.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.date_label)

        market_row = QHBoxLayout()
        self.stock_status_label = QLabel("● 股市：已收盘")
        self.stock_status_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: bold;")
        
        self.cal_btn = QPushButton("📅 查看休市日历")
        self.cal_btn.setStyleSheet("""
            QPushButton {
                background-color: #262b36;
                color: #f87171;
                border: 1px solid rgba(248, 113, 113, 0.3);
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
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

        self.silver_board = QLabel()
        self.silver_board.setAlignment(Qt.AlignCenter)
        self.update_silver_board_ui()
        c_layout.addWidget(self.silver_board)

        self.silver_status_label = QLabel("● 白银非交易时段 (距开盘 01:55:02)")
        self.silver_status_label.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.silver_status_label)

        self.next_holiday_label = QLabel("📌 下一休市：加载中...")
        self.next_holiday_label.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.next_holiday_label)

        self.apply_theme(self.current_bg_color, self.current_time_color, self.current_card_bg, self.current_accent)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)
        self.update_clock()

        self.resize(340, 420)

    def init_quote_thread(self):
        self.quote_worker = SilverQuoteWorker()
        self.quote_worker.data_fetched.connect(self.on_silver_data_updated)
        self.quote_worker.start()

    def on_silver_data_updated(self, info):
        self.silver_data.update(info)
        self.update_silver_board_ui()

    def update_silver_board_ui(self):
        d = self.silver_data
        try:
            chg_val = float(d['change'])
        except Exception:
            chg_val = 0.0
        
        color_hex = "#ef4444" if chg_val >= 0 else "#22c55e"
        arrow = "▲" if chg_val >= 0 else "▼"

        html_text = f"""
        <div style="font-family: Consolas, monospace; line-height: 1.3; text-align: center;">
            <div style="font-size: 13px; font-weight: bold; color: #94a3b8; margin-bottom: 2px;">沪银主力 AG2702</div>
            <div style="font-size: 26px; font-weight: bold; color: #ffffff; letter-spacing: 0.5px;">{d['price']}</div>
            <div style="font-size: 13px; font-weight: bold; color: {color_hex}; margin-top: 2px;">{arrow} {d['change']} ({d['change_pct']})</div>
            <div style="font-size: 11px; color: #64748b; margin-top: 5px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 3px;">
                成交量: {d['volume']} &nbsp;|&nbsp; 持仓量: {d['open_interest']}
            </div>
        </div>
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

        self.weekday_label.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg};
                color: #e2e8f0;
                font-size: 20px;
                font-weight: bold;
                border-radius: 8px;
                padding: 6px;
                border: 1px solid rgba(255,255,255,0.06);
            }}
        """)

        self.time_label.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg};
                color: {time_color};
                font-size: 32px;
                font-weight: bold;
                font-family: Consolas, monospace;
                border-radius: 8px;
                padding: 8px;
                border: 1px solid rgba(255,255,255,0.06);
            }}
        """)

        self.date_label.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg};
                color: #94a3b8;
                font-size: 14px;
                border-radius: 8px;
                padding: 6px;
                border: 1px solid rgba(255,255,255,0.06);
            }}
        """)

        self.silver_board.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg};
                border-radius: 8px;
                padding: 8px;
                border: 1px solid rgba(255,255,255,0.06);
            }}
        """)

        self.silver_status_label.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg};
                color: #94a3b8;
                font-size: 13px;
                border-radius: 8px;
                padding: 6px;
                border: 1px solid rgba(255,255,255,0.06);
            }}
        """)

        self.next_holiday_label.setStyleSheet(f"""
            QLabel {{
                background-color: {card_bg};
                color: #38bdf8;
                font-size: 13px;
                font-weight: bold;
                border-radius: 8px;
                padding: 6px;
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

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec_()

    def show_calendar(self):
        dialog = MarketCalendarDialog(self)
        dialog.exec_()

    def update_clock(self):
        now = datetime.datetime.now()
        week_days = ['星期一','星期二','星期三','星期四','星期五','星期六','星期日']
        
        self.weekday_label.setText(week_days[now.weekday()])
        self.time_label.setText(now.strftime("%H:%M:%S"))
        self.date_label.setText(now.strftime("%Y年%m月%d日"))

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
                self.silver_status_label.setText(f"● 白银：{reason}")
            else:
                self.update_silver_countdown(now)
        elif now.weekday() >= 5:
            self.stock_status_label.setText("● 股市：周末休市")
            self.silver_status_label.setText("● 白银：周末休市 (非交易日)")
        else:
            t = now.time()
            if datetime.time(9, 30) <= t <= datetime.time(15, 0):
                self.stock_status_label.setText("● 股市：交易中")
            else:
                self.stock_status_label.setText("● 股市：已收盘")
            
            self.update_silver_countdown(now)

    def update_silver_countdown(self, now):
        current_time = now.time()
        
        t_night_open = datetime.time(21, 0, 0)
        t_morning_open = datetime.time(9, 0, 0)

        is_trading = False
        if (datetime.time(9, 0) <= current_time <= datetime.time(11, 30)) or            (datetime.time(13, 30) <= current_time <= datetime.time(15, 0)) or            (datetime.time(21, 0) <= current_time) or            (current_time <= datetime.time(2, 30)):
            is_trading = True

        if is_trading:
            self.silver_status_label.setText("● 白银期货：交易中 (Live)")
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
                self.silver_status_label.setText(f"● 白银非交易时段 (距开盘 {hours:02d}:{minutes:02d}:{seconds:02d})")
            else:
                self.silver_status_label.setText("● 白银即将开盘...")

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
                    next_reason = info.get("reason", "休_市") if isinstance(info, dict) else "休市"
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
        print("Starting app...")
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        print("Initializing window...")
        window = ClockWindow()
        print("Showing window...")
        window.show()
        print("Entering event loop...")
        sys.exit(app.exec_())
    except Exception as e:
        traceback.print_exc()
        input("Press Enter to exit...")
