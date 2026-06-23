#!/bin/bash
# ============================================================
#  合同归档管理系统 — 停止脚本
#  用法: ./stop.sh
# ============================================================
echo "============================================"
echo "  停止合同归档管理系统"
echo "============================================"
echo ""

# 1. 按端口杀（最可靠）
echo "[1/2] 终止8000端口进程..."
PID=$(lsof -ti:8000 2>/dev/null || true)
if [ -n "$PID" ]; then
    echo "  - 终止 PID: $PID"
    kill -15 "$PID" 2>/dev/null || true
    sleep 1
    # 如果还没死，强杀
    kill -9 "$PID" 2>/dev/null || true 2>/dev/null
    echo "  - 已终止"
else
    echo "  - 8000端口无监听进程"
fi

# 2. 确认端口已释放
echo ""
echo "[2/2] 确认端口已释放..."
for i in $(seq 1 5); do
    if lsof -ti:8000 > /dev/null 2>&1; then
        echo "  - 端口仍被占用，重试... ($i/5)"
        PID=$(lsof -ti:8000 2>/dev/null)
        kill -9 "$PID" 2>/dev/null || true
        sleep 1
    else
        echo "  - 8000端口已释放"
        break
    fi
done

echo ""
echo "============================================"
echo "  服务已停止"
echo "============================================"
