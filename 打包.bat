@echo off
chcp 65001 >null
echo [1/4] 正在清理旧的打包残留缓存...
rd /s /q build >null
rd /s /q dist >null
del /f /q *.spec >null

echo [2/4] 正在执行 PyInstaller 高净空打包...
:: 如果你的主入口是 create.py 保持不变；如果是其他主程序请将 create.py 替换为你的文件名
pyinstaller --clean --noconsole --onefile --icon=icon.ico --add-data "wx_bot_monitor.py;." create.py

if %errorlevel% neq 0 (
    echo ========================================================
    echo [错误] 打包失败！检测到文件被占用或语法错误！
    echo ========================================================
    pause
    exit /b %errorlevel%
)

echo [4/4] 打包成功！新版程序已生成在 dist 目录。
pause