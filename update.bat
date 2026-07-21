@echo off
chcp 65001 >nul
cd /d "%~dp0%"
echo ========================================
echo     BiddingInformation 一键更新脚本
echo ========================================
echo.

REM 1. 激活虚拟环境并运行爬虫
echo [1/4] 正在运行爬虫...
call venv\Scripts\activate
python -m scripts.bidding_scraper.main --output output/bidding_feed.xml
if errorlevel 1 (
    echo [错误] 爬虫运行失败，请检查日志。
    pause
    exit /b 1
)

REM 2. 生成静态 HTML
echo [2/4] 正在生成静态页面...
python scripts/serve_web.py --output output/index.html
if errorlevel 1 (
    echo [错误] 静态页面生成失败。
    pause
    exit /b 1
)

REM 3. 检查是否有变更
echo [3/4] 检查文件变更...
git add output/
git diff --cached --quiet
if errorlevel 0 (
    echo 没有检测到新数据，跳过提交。
) else (
    REM 有变更，提交并推送
    echo 检测到数据更新，正在提交...
    git commit -m "自动更新招标数据 (%date% %time%)"
    if errorlevel 1 (
        echo [错误] Git 提交失败。
        pause
        exit /b 1
    )
    echo [4/4] 正在推送到 GitHub...
    git push origin master
    if errorlevel 1 (
        echo [错误] Git 推送失败，请检查网络和权限。
        pause
        exit /b 1
    )
    echo.
    echo ========================================
    echo     更新完成！GitHub Actions 将自动部署
    echo ========================================
)

REM 4. 退出虚拟环境
call deactivate

echo.
echo 按任意键退出...
pause >nul