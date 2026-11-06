import sys
import calendar
from datetime import datetime, date, time, timedelta
import os
import winreg
import traceback
import webbrowser
from PyQt5.QtCore import Qt, QTimer, QPoint, QSettings, QSharedMemory
from PyQt5.QtWidgets import (
    QApplication, QDialog, QGridLayout, 
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
    QCheckBox, QSlider, QFormLayout, QSystemTrayIcon, QMenu, QAction, QStyle, QMessageBox
)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedSize(300, 260)
        self.parent_widget = parent
        self.setStyleSheet("QDialog { background-color: #2b3035; color: #ffffff; border-radius: 10px; } QLabel { color: #ffffff; font-size: 13px; } QCheckBox { color: #ffffff; spacing: 8px; } QPushButton { background-color: #34495e; color: #ffffff; border-radius: 6px; padding: 6px 14px; font-weight: bold; border: 1px solid rgba(255,255,255,0.1); } QPushButton:hover { background-color: #2980b9; }")

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.ontop_chk = QCheckBox("窗口总在最前端")
        self.ontop_chk.setChecked(self.parent_widget.is_on_top if self.parent_widget else True)
        self.ontop_chk.stateChanged.connect(self.toggle_ontop)
        form_layout.addRow(self.ontop_chk)

        self.hide_chk = QCheckBox("关闭时隐藏到托盘")
        self.hide_chk.setChecked(self.parent_widget.close_to_tray if self.parent_widget else True)
        self.hide_chk.stateChanged.connect(self.toggle_hide)
        form_layout.addRow(self.hide_chk)

        self.autostart_chk = QCheckBox("开机自动启动")
        self.autostart_chk.setChecked(self.check_autostart_status())
        self.autostart_chk.stateChanged.connect(self.toggle_autostart)
        form_layout.addRow(self.autostart_chk)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(50, 255)
        self.opacity_slider.setValue(self.parent_widget.current_opacity if self.parent_widget else 245)
        self.opacity_slider.valueChanged.connect(self.change_opacity)
        form_layout.addRow("背景透明度:", self.opacity_slider)

        layout.addLayout(form_layout)
        close_btn = QPushButton("确定")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def toggle_ontop(self, state):
        if self.parent_widget:
            is_on = (state == Qt.Checked)
            self.parent_widget.is_on_top = is_on
            flags = self.parent_widget.windowFlags()
            if is_on:
                self.parent_widget.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
            else:
                self.parent_widget.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
            self.parent_widget.show()
            self.parent_widget.save_settings()

    def toggle_hide(self, state):
        if self.parent_widget:
            self.parent_widget.close_to_tray = (state == Qt.Checked)
            self.parent_widget.save_settings()

    def check_autostart_status(self):
        key_path = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        app_name = "MarketClockWidget"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, app_name)
            winreg.CloseKey(key)
            return True
        except WindowsError:
            return False

    def toggle_autostart(self, state):
        key_path = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        app_name = "MarketClockWidget"
        script_path = os.path.abspath(sys.argv[0])
        python_exe = sys.executable.replace("python.exe", "pythonw.exe")
        cmd = f'"{python_exe}" "{script_path}"'
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if state == Qt.Checked:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except WindowsError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print("设置开机自启失败:", e)

    def change_opacity(self, value):
        if self.parent_widget:
            self.parent_widget.current_opacity = value
            style = "QWidget { background-color: rgba(43, 48, 53, " + str(value) + "); border-radius: 16px; border: 1px solid rgba(255,255,255,0.15); }"
            self.parent_widget.card.setStyleSheet(style)
            self.parent_widget.save_settings()


class CalendarDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("A股/港股动态休市日历")
        self.setFixedSize(460, 580)
        
        now = datetime.now()
        self.current_year = now.year
        self.current_month = now.month

        self.setStyleSheet("QDialog { background-color: #2b3035; color: #ffffff; border-radius: 12px; } QLabel { color: #ffffff; font-size: 13px; } QPushButton { background-color: #34495e; color: #ffffff; border-radius: 6px; padding: 6px 14px; font-weight: bold; border: 1px solid rgba(255,255,255,0.1); } QPushButton:hover { background-color: #2980b9; }")

        layout = QVBoxLayout(self)
        top_bar = QWidget()
        top_bar.setStyleSheet("QWidget { background-color: #1f3a60; border-radius: 8px; padding: 4px; }")
        top_layout = QHBoxLayout(top_bar)
        
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(36, 30)
        self.prev_btn.clicked.connect(self.prev_month)
        
        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(36, 30)
        self.next_btn.clicked.connect(self.next_month)
        
        self.month_title = QLabel()
        self.month_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        self.month_title.setAlignment(Qt.AlignCenter)
        
        top_layout.addWidget(self.prev_btn)
        top_layout.addStretch()
        top_layout.addWidget(self.month_title)
        top_layout.addStretch()
        top_layout.addWidget(self.next_btn)
        layout.addWidget(top_bar)

        week_widget = QWidget()
        week_layout = QGridLayout(week_widget)
        week_layout.setContentsMargins(0, 5, 0, 5)
        weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
        for i, w in enumerate(weekdays):
            lbl = QLabel(w)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #e74c3c; font-size: 14px; font-weight: bold;" if i in [0, 6] else "color: #d0d0d0; font-size: 14px; font-weight: bold;")
            week_layout.addWidget(lbl, 0, i)
        layout.addWidget(week_widget)

        self.days_widget = QWidget()
        self.days_layout = QGridLayout(self.days_widget)
        self.days_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.days_widget)

        btn_layout = QHBoxLayout()
        web_btn = QPushButton("🌐 打开东财官方休市网页")
        web_btn.setStyleSheet("background-color: #2980b9; color: #ffffff;")
        web_btn.clicked.connect(lambda: webbrowser.open("https://data.eastmoney.com/dcrl/close.html"))
        
        close_btn = QPushButton("关闭面板")
        close_btn.clicked.connect(self.close)
        
        btn_layout.addWidget(web_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.update_calendar_grid()

    def prev_month(self):
        self.current_month -= 1
        if self.current_month < 1:
            self.current_month = 12
            self.current_year -= 1
        self.update_calendar_grid()

    def next_month(self):
        self.current_month += 1
        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1
        self.update_calendar_grid()

    @staticmethod
    def get_holiday_info(year, month, day):
        current_date = date(year, month, day)
        is_weekend = (current_date.weekday() >= 5)
        
        tips = []
        if is_weekend:
            tips.append("周末固定休市")
            
        if year == 2026:
            if month == 1 and day in [1, 2] and not is_weekend:
                tips.append("元旦休市")
            elif month == 2 and 16 <= day <= 20 and not is_weekend:
                tips.append("春节休市")
            elif month == 4 and day in [3, 6] and not is_weekend:
                tips.append("清明节休市")
            elif month == 5 and day in [1, 4, 5] and not is_weekend:
                tips.append("劳动节休市")
            elif month == 6 and day in [19, 22] and not is_weekend:
                tips.append("端午节休市")
            elif month == 9 and day in [25, 28] and not is_weekend:
                tips.append("中秋节休市")
            elif month == 10 and 1 <= day <= 7 and not is_weekend:
                tips.append("国庆节休市")

        is_closed = is_weekend or len(tips) > 0
        tip_str = f"{year}年{month}月{day}日休市原因：\n" + "\n".join(tips) if tips else f"{year}年{month}月{day}日：正常交易日"
        return str(day), tip_str, is_weekend, is_closed

    def update_calendar_grid(self):
        y_str = str(self.current_year)
        m_str = str(self.current_month)
        self.month_title.setText(y_str + "年 " + m_str + "月")
        for i in reversed(range(self.days_layout.count())):
            w = self.days_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdayscalendar(self.current_year, self.current_month)
        
        for r_idx, week in enumerate(month_days):
            for c_idx, day in enumerate(week):
                if day == 0:
                    btn = QPushButton("")
                    btn.setEnabled(False)
                else:
                    marker, tip, is_weekend, is_closed = CalendarDialog.get_holiday_info(self.current_year, self.current_month, day)
                    btn = QPushButton(marker)
                    btn.clicked.connect(lambda checked, t=tip: QMessageBox.information(self, "日期休市详情", t))
                    
                    if is_weekend:
                        btn.setStyleSheet("background-color: rgba(46, 204, 113, 0.2); color: #2ecc71; border-radius: 6px; font-weight: bold;")
                    elif is_closed:
                        btn.setStyleSheet("background-color: rgba(231, 76, 60, 0.2); color: #e74c3c; border-radius: 6px; font-weight: bold;")
                    else:
                        btn.setStyleSheet("background-color: #34495e; color: #ffffff; border-radius: 6px;")

                btn.setFixedHeight(50)
                self.days_layout.addWidget(btn, r_idx, c_idx)


class MarketClockWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.drag_position = QPoint()
        self.is_locked = False
        
        self.settings = QSettings("MarketClockOrg", "MarketClockApp")
        self.load_settings()

        self.init_ui()
        self.init_tray()

    def load_settings(self):
        self.close_to_tray = self.settings.value("close_to_tray", True, type=bool)
        self.is_on_top = self.settings.value("is_on_top", True, type=bool)
        self.current_opacity = self.settings.value("opacity", 245, type=int)
        
        pos = self.settings.value("pos")
        if pos:
            self.move(pos)

    def save_settings(self):
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("close_to_tray", self.close_to_tray)
        self.settings.setValue("is_on_top", self.is_on_top)
        self.settings.setValue("opacity", self.current_opacity)

    def init_ui(self):
        flags = Qt.FramelessWindowHint
        if self.is_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.card = QWidget()
        style = "QWidget { background-color: rgba(43, 48, 53, " + str(self.current_opacity) + "); border-radius: 16px; border: 1px solid rgba(255,255,255,0.15); }"
        self.card.setStyleSheet(style)
        
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 15, 20, 15)
        
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        
        self.lock_btn = QPushButton("🔓")
        self.lock_btn.setFixedSize(26, 26)
        self.lock_btn.setToolTip("锁定窗口位置")
        self.lock_btn.setStyleSheet("QPushButton { background: transparent; color: #ffffff; border: none; font-size: 14px; } QPushButton:hover { background: rgba(255,255,255,0.1); border-radius: 4px; }")
        self.lock_btn.clicked.connect(self.toggle_lock)
        
        self.setting_btn = QPushButton("⚙")
        self.setting_btn.setFixedSize(26, 26)
        self.setting_btn.setToolTip("设置")
        self.setting_btn.setStyleSheet("QPushButton { background: transparent; color: #ffffff; border: none; font-size: 14px; } QPushButton:hover { background: rgba(255,255,255,0.1); border-radius: 4px; }")
        self.setting_btn.clicked.connect(self.open_settings)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setToolTip("关闭")
        close_btn.setStyleSheet("QPushButton { background: transparent; color: #ffffff; border: none; font-size: 14px; } QPushButton:hover { background: rgba(231,76,60,0.8); border-radius: 4px; }")
        close_btn.clicked.connect(self.close)
        
        top_bar.addWidget(self.lock_btn)
        top_bar.addWidget(self.setting_btn)
        top_bar.addStretch()
        top_bar.addWidget(close_btn)
        card_layout.addLayout(top_bar)

        self.weekday_label = QLabel("星期一")
        self.weekday_label.setAlignment(Qt.AlignCenter)
        self.weekday_label.setStyleSheet("color: #ffffff; font-size: 32px; font-weight: bold;")
        card_layout.addWidget(self.weekday_label)

        self.time_label = QLabel("00:00:00")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("color: #ffffff; font-size: 44px; font-weight: 300;")
        card_layout.addWidget(self.time_label)

        self.date_label = QLabel("2026年11月03日")
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet("color: #d0d0d0; font-size: 16px;")
        card_layout.addWidget(self.date_label)

        # 股市状态栏与“查看休市日历”按钮放在同一行，完美填满右侧空位
        footer_layout = QHBoxLayout()
        self.market_status_label = QLabel("📈 股市: 检查中...")
        self.market_status_label.setStyleSheet("color: #2ecc71; font-size: 12px; font-weight: bold;")
        
        self.holiday_btn = QPushButton("📅 查看休市日历")
        self.holiday_btn.setMinimumWidth(140)
        self.holiday_btn.setStyleSheet("QPushButton { background-color: rgba(255, 255, 255, 0.08); color: #e74c3c; font-size: 12px; font-weight: bold; border: 1px solid rgba(231, 76, 60, 0.3); border-radius: 6px; padding: 4px 8px; text-align: center; } QPushButton:hover { background-color: rgba(231, 76, 60, 0.2); color: #ffffff; }")
        self.holiday_btn.clicked.connect(lambda: CalendarDialog(self).exec_())
        
        footer_layout.addWidget(self.market_status_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.holiday_btn)
        card_layout.addLayout(footer_layout)

        # 沪银行情看板：使用独立的容器 QWidget 作为背景壳，内部放 QLabel，在 PyInstaller 打包后 100% 绝对稳定！
        self.quote_container = QWidget()
        self.quote_layout = QHBoxLayout(self.quote_container)
        self.quote_layout.setContentsMargins(8, 4, 8, 4)
        
        self.quote_label = QLabel("📈 沪银2702: 12402 ▼ -227 (-1.80%)")
        self.quote_label.setAlignment(Qt.AlignCenter)
        self.quote_layout.addWidget(self.quote_label)
        
        self.update_quote_style(-227)
        card_layout.addWidget(self.quote_container)

        # 白银期货状态栏
        self.silver_status_label = QLabel("⚪ 白银期货: 检查中...")
        self.silver_status_label.setAlignment(Qt.AlignCenter)
        self.silver_status_label.setStyleSheet("color: #f39c12; font-size: 12px; font-weight: bold; margin-top: 4px;")
        card_layout.addWidget(self.silver_status_label)
        
        main_layout.addWidget(self.card)
        self.setLayout(main_layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)
        self.update_clock()
        self.resize(360, 310)

    def update_quote_style(self, change_val):
        """根据涨跌值动态调整行情看板容器颜色 (使用容器 QWidget 背景，打包后绝对不失效)"""
        if change_val >= 0:
            self.quote_container.setStyleSheet(
                "background-color: #fdedec; border: 1px solid #f5b7b1; border-radius: 6px; margin-top: 4px;"
            )
            self.quote_label.setStyleSheet(
                "color: #c0392b; font-size: 13px; font-weight: bold; background: transparent; border: none;"
            )
        else:
            self.quote_container.setStyleSheet(
                "background-color: #eafaf1; border: 1px solid #a9dfbf; border-radius: 6px; margin-top: 4px;"
            )
            self.quote_label.setStyleSheet(
                "color: #27ae60; font-size: 13px; font-weight: bold; background: transparent; border: none;"
            )

    def init_tray(self):
        try:
            icon = self.style().standardIcon(QStyle.SP_FileDialogInfoView)
            self.tray_icon = QSystemTrayIcon(icon, self)
            self.tray_icon.setToolTip("A股/白银市场监控时钟")

            tray_menu = QMenu()
            show_action = QAction("显示主界面", self)
            show_action.triggered.connect(self.showNormal)
            quit_action = QAction("完全退出", self)
            quit_action.triggered.connect(QApplication.quit)

            tray_menu.addAction(show_action)
            tray_menu.addSeparator()
            tray_menu.addAction(quit_action)

            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self.on_tray_activated)
            self.tray_icon.show()
        except Exception as e:
            print("托盘初始化提示:", e)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.raise_()

    def closeEvent(self, event):
        self.save_settings()
        if self.close_to_tray:
            event.ignore()
            self.hide()
        else:
            event.accept()

    def toggle_lock(self):
        self.is_locked = not self.is_locked
        if self.is_locked:
            self.lock_btn.setText("🔒")
            self.lock_btn.setToolTip("已锁定窗口位置（点击解锁）")
        else:
            self.lock_btn.setText("🔓")
            self.lock_btn.setToolTip("锁定窗口位置")

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec_()

    def update_clock(self):
        now = datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        self.weekday_label.setText(weekdays[now.weekday()])
        self.time_label.setText(now.strftime("%H:%M:%S"))
        self.date_label.setText(now.strftime("%Y年%m月%d日"))
        
        t_str = now.strftime("%H:%M")
        full_t_str = now.strftime("%H:%M:%S")
        _, tip_str, is_weekend, is_closed = CalendarDialog.get_holiday_info(now.year, now.month, now.day)

        is_trading_time = False
        if not is_closed:
            if ("09:30:00" <= full_t_str <= "11:30:00") or ("13:00:00" <= full_t_str <= "15:00:00"):
                is_trading_time = True

        if is_closed:
            self.market_status_label.setText("🔴 股市: 今日休市")
            self.market_status_label.setStyleSheet("color: #e74c3c;")
        elif is_trading_time:
            if full_t_str <= "11:30:00":
                close_t = datetime.combine(now.date(), time(11, 30, 0))
                diff = close_t - now
                secs = int(diff.total_seconds())
                if secs > 0:
                    h, rem = divmod(secs, 3600)
                    m, s = divmod(rem, 60)
                    self.market_status_label.setText(f"🟢 距上午收盘 {h:02d}:{m:02d}:{s:02d}")
                else:
                    self.market_status_label.setText("🟢 股市: 交易中")
            elif "13:00:00" <= full_t_str <= "15:00:00":
                close_t = datetime.combine(now.date(), time(15, 0, 0))
                diff = close_t - now
                secs = int(diff.total_seconds())
                if secs > 0:
                    h, rem = divmod(secs, 3600)
                    m, s = divmod(rem, 60)
                    self.market_status_label.setText(f"🟢 距下午收盘 {h:02d}:{m:02d}:{s:02d}")
                else:
                    self.market_status_label.setText("🟢 15:00 正式收盘")
            else:
                self.market_status_label.setText("🟢 股市: 交易中")
            self.market_status_label.setStyleSheet("color: #2ecc71;")
        else:
            if "09:15:00" <= full_t_str < "09:25:00":
                self.market_status_label.setText("🟡 股市: 集合竞价中")
                self.market_status_label.setStyleSheet("color: #f1c40f;")
            elif "09:25:00" <= full_t_str < "09:30:00":
                self.market_status_label.setText("🟡 股市: 等待开盘")
                self.market_status_label.setStyleSheet("color: #f39c12;")
            elif full_t_str < "09:15:00":
                self.market_status_label.setText("⚪ 股市: 未开盘")
                self.market_status_label.setStyleSheet("color: #95a5a6;")
            elif "11:30:00" < full_t_str < "13:00:00":
                self.market_status_label.setText("🟡 股市: 午休中")
                self.market_status_label.setStyleSheet("color: #f1c40f;")
            else:
                self.market_status_label.setText("⚪ 股市: 已收盘")
                self.market_status_label.setStyleSheet("color: #95a5a6;")

        # 白银期货（沪银）实时状态判定及开盘倒计时计算
        weekday = now.weekday()
        is_weekend_silver = (weekday >= 5)
        is_early_mon = (weekday == 0 and "02:30:00" < full_t_str < "09:00:00")
        
        if is_weekend_silver or is_early_mon:
            if weekday == 5 or weekday == 6:
                days_to_mon = (0 - weekday) % 7
                if days_to_mon == 0:
                    days_to_mon = 7
                next_open = datetime.combine(now.date() + timedelta(days=days_to_mon), time(21, 0, 0))
            elif is_early_mon:
                next_open = datetime.combine(now.date(), time(9, 0, 0))
            else:
                next_open = datetime.combine(now.date(), time(21, 0, 0))
            
            diff = next_open - now
            secs = int(diff.total_seconds())
            if secs > 0:
                d, rem = divmod(secs, 86400)
                h, rem = divmod(rem, 3600)
                m, s = divmod(rem, 60)
                if d > 0:
                    countdown_str = f"距开盘: {d}天 {h:02d}:{m:02d}:{s:02d}"
                else:
                    countdown_str = f"距开盘: {h:02d}:{m:02d}:{s:02d}"
            else:
                countdown_str = "即将开盘"

            if weekday == 5 or weekday == 6:
                self.silver_status_label.setText(f"⚪ 白银期货: 周末休市 ({countdown_str})")
            else:
                self.silver_status_label.setText(f"⚪ 白银期货: 非交易时段 ({countdown_str})")
            self.silver_status_label.setStyleSheet("color: #95a5a6;")
        else:
            if "08:55:00" <= full_t_str < "09:00:00":
                self.silver_status_label.setText("🟡 白银日盘: 集合竞价中")
                self.silver_status_label.setStyleSheet("color: #f1c40f;")
            elif ("09:00:00" <= full_t_str <= "10:15:00") or ("10:30:00" <= full_t_str <= "11:30:00") or ("13:30:00" <= full_t_str <= "15:00:00"):
                self.silver_status_label.setText("🟢 白银日盘: 交易中")
                self.silver_status_label.setStyleSheet("color: #2ecc71;")
            elif ("10:15:00" < full_t_str < "10:30:00") or ("11:30:00" < full_t_str < "13:30:00"):
                if full_t_str < "10:30:00":
                    next_open = datetime.combine(now.date(), time(10, 30, 0))
                elif full_t_str < "13:30:00":
                    next_open = datetime.combine(now.date(), time(13, 30, 0))
                else:
                    next_open = datetime.combine(now.date(), time(21, 0, 0))
                
                diff = next_open - now
                secs = int(diff.total_seconds())
                h, rem = divmod(secs, 3600)
                m, s = divmod(rem, 60)
                self.silver_status_label.setText(f"🟡 白银盘中休市 (距开盘 {h:02d}:{m:02d}:{s:02d})")
                self.silver_status_label.setStyleSheet("color: #f1c40f;")
            elif "20:55:00" <= full_t_str < "21:00:00":
                self.silver_status_label.setText("🟡 白银夜盘: 集合竞价中 ⚠️ 注意风控")
                self.silver_status_label.setStyleSheet("color: #e67e22;")
            elif ("21:00:00" <= full_t_str) or (full_t_str <= "02:30:00"):
                self.silver_status_label.setText("🌙 🟢 白银夜盘: 正在火热交易中")
                self.silver_status_label.setStyleSheet("color: #00e676;")
            else:
                if full_t_str < "08:55:00":
                    next_open = datetime.combine(now.date(), time(9, 0, 0))
                else:
                    next_open = datetime.combine(now.date(), time(21, 0, 0))
                
                diff = next_open - now
                secs = int(diff.total_seconds())
                h, rem = divmod(secs, 3600)
                m, s = divmod(rem, 60)
                self.silver_status_label.setText(f"⚪ 白银非交易时段 (距开盘 {h:02d}:{m:02d}:{s:02d})")
                self.silver_status_label.setStyleSheet("color: #95a5a6;")

    def mousePressEvent(self, event):
        if not self.is_locked and event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if not self.is_locked and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            self.save_settings()
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 保证全局单例运行：若已有实例 in 运行则直接退出或提示
    shared_memory = QSharedMemory("MarketClockUniqueInstanceKey")
    if not shared_memory.create(1):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("提示")
        msg.setText("市场时钟程序已经在运行中啦！\n请检查任务栏右下角托盘或桌面窗口。")
        msg.exec_()
        sys.exit(0)

    try:
        app.setQuitOnLastWindowClosed(False)
        clock = MarketClockWidget()
        clock.show()
        sys.exit(app.exec_())
    except Exception as e:
        error_msg = traceback.format_exc()
        print(error_msg)
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("程序运行出错")
        msg.setText("程序发生异常崩溃：")
        msg.setDetailedText(error_msg)
        msg.exec_()
