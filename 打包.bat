@echo off
chcp 65001 >nul
echo [1/4] 正在强行清理后台残留的旧进程...
taskkill /f /im create.py 2>nul
taskkill /f /im python.exe 2>nul

echo [2/4] 正在彻底清除 PyInstaller 编译缓存...
rd /s /q build 2>nul
rd /s /q dist 2>nul
del /f /q *.spec 2>nul

echo [3/4] 正在执行 PyInstaller 高净空打包...
:: 加 --clean 彻底清理缓存，--noconsole 去除黑窗口，--icon 指定软件图标
pyinstaller --clean --noconsole --onefile --icon=icon.ico --version-file=version.txt create.py

if %errorlevel% neq 0 (
    echo ========================================================
    echo [错误] 打包失败！检测到文件被占用或语法错误！
    echo ========================================================
    pause
    exit /b %errorlevel%
)

echo [4/4] 打包成功！新版 create.exe 已生成在 dist 目录。
pause