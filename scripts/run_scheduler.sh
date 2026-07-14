#!/bin/bash
# =============================================================================
# 招标信息爬虫定时任务脚本
# =============================================================================
# 
# 使用说明：
# 
# 1. 给脚本添加执行权限：
#    chmod +x scripts/run_scheduler.sh
# 
# 2. 配置定时任务（Linux/Mac）：
#    # 编辑 crontab
#    crontab -e
#    
#    # 添加以下行（每天早上8点执行）：
#    0 8 * * * /path/to/IronTowerInformation/scripts/run_scheduler.sh >> /path/to/IronTowerInformation/output/scheduler.log 2>&1
#    
#    # 保存退出
# 
# 3. 配置定时任务（Windows）：
#    # 打开"任务计划程序"
#    # 创建基本任务
#    # 名称：招标信息爬虫
#    # 触发器：每天 8:00
#    # 操作：启动程序
#    # 程序：python
#    # 参数：-m scripts.bidding_scraper
#    # 起始位置：项目根目录
# 
# 4. 使用 Git Hooks（可选）：
#    # 如果需要每次 git push 时自动运行，可以配置 pre-push hook
#    # 编辑 .git/hooks/pre-push，添加：
#    # #!/bin/bash
#    # ./scripts/run_scheduler.sh
# 
# =============================================================================

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 切换到项目目录
cd "$PROJECT_DIR"

# 日志文件
LOG_FILE="$PROJECT_DIR/output/scheduler.log"

# 确保输出目录存在
mkdir -p "$PROJECT_DIR/output"

# 记录开始时间
echo "========================================" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 定时任务开始执行" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# 运行爬虫
python -m scripts.bidding_scraper >> "$LOG_FILE" 2>&1

# 记录结束时间
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 定时任务执行完成" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# 清理30天前的日志（保留最近30天）
if [ -f "$LOG_FILE" ]; then
    # 获取日志文件大小
    LOG_SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null)
    # 如果日志文件超过10MB，只保留最后5MB
    if [ "$LOG_SIZE" -gt 10485760 ]; then
        tail -c 5242880 "$LOG_FILE" > "$LOG_FILE.tmp"
        mv "$LOG_FILE.tmp" "$LOG_FILE"
    fi
fi
