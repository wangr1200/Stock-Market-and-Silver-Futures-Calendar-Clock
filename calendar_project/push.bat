@echo off
chcp 65001 >nul
echo =========================================
echo       正在一键推送代码到 GitHub...
echo =========================================
echo.

git status
git add .

set /p msg=请输入提交说明 (直接回车默认使用时间戳): 
if "%msg%"=="" (
    set msg=auto update: %date% %time%
)

git commit -m "%msg%"
echo.
echo 正在推送到云端远程仓库...
git push origin main

echo.
echo =========================================
echo         推送完成！窗口即将在 3 秒后关闭
echo =========================================
timeout /t 3 >nul