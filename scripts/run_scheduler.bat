@echo off
REM =============================================================================
REM 招标信息爬虫定时任务脚本（Windows 版本）
REM =============================================================================
REM 
REM 使用说明：
REM 
REM 1. 配置定时任务：
REM    # 打开"任务计划程序"（在开始菜单搜索"任务计划"）
REM    # 点击"创建基本任务"
REM    # 名称：招标信息爬虫
REM    # 触发器：每天 8:00（或你选择的时间）
REM    # 操作：启动程序
REM    # 程序或脚本：python
REM    # 添加参数：-m scripts.bidding_scraper
REM    # 起始于：项目根目录路径（如 D:\my-project\IronTowerInformation）
REM 
REM 2. 或者使用批处理文件：
REM    # 在"操作"中选择"启动程序"
REM    # 程序：选择本文件（run_scheduler.bat）
REM    # 起始于：项目根目录路径
REM 
REM =============================================================================

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..

REM 切换到项目目录
cd /d "%PROJECT_DIR%"

REM 日志文件
set LOG_FILE=%PROJECT_DIR%\output\scheduler.log

REM 确保输出目录存在
if not exist "%PROJECT_DIR%\output" mkdir "%PROJECT_DIR%\output"

REM 记录开始时间
echo ======================================== >> "%LOG_FILE%"
echo [%date% %time%] 定时任务开始执行 >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

REM 运行爬虫
python -m scripts.bidding_scraper >> "%LOG_FILE%" 2>&1

REM 记录结束时间
echo [%date% %time%] 定时任务执行完成 >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"
