@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================================
echo           正在一键同步并推送代码到 GitHub...
echo ========================================================
echo.

echo [1/4] 正在拉取远程最新变更并合并...
git pull --rebase origin main
if errorlevel 1 (
    echo [警告] 拉取远程变更时遇到冲突或网络波动，尝试继续本地提交...
)
echo.

echo [2/4] 检查本地文件修改状态...
git status -s
git add -A
echo.

set "msg="
set /p msg=请输入提交说明 (直接回车默认使用时间戳): 
if "%msg%"=="" (
    set "msg=auto update: %date% %time%"
)

echo.
echo [3/4] 正在提交本地更改: "%msg%"
git commit --allow-empty -m "%msg%"
echo.

echo [4/4] 正在强制同步推送到云端远程仓库...
git push origin main
if errorlevel 1 (
    echo.
    echo [提示] 常规推送受阻，正在尝试强制同步覆盖远程分支...
    git push -f origin main
)

echo.
echo ========================================================
if errorlevel 1 (
    echo    [失败] 推送失败！请检查网络连接或代理设置。
    echo ========================================================
    pause
) else (
    echo    [成功] 推送完成！GitHub 云端已更新为最新版本。
    echo ========================================================
    timeout /t 3 >nul
)
