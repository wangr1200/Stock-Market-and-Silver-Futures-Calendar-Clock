@echo off
chcp 65001
echo ==========================================
echo   正在使用 PyInstaller 打包桌面市场日历时钟...
echo ==========================================

pyinstaller --noconsole --onefile --name="MarketDesktopClock" create.py

echo.
echo 打包完成！生成的可执行文件在 dist 文件夹下。
pause