@echo off
chcp 65001 >nul
echo 正在开始打包单文件 EXE 应用程序 (包含 icon.ico 图标)...

pyinstaller --noconfirm --onefile --windowed --icon="icon.ico" --add-data "icon.ico;." create_v7.py

echo.
echo 打包完成！生成的单文件 EXE 已存放在 dist 目录下。
pause