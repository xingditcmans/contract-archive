#!/bin/bash
# ============================================================
#  合同归档管理系统 — Linux/macOS 启动脚本
#  用法: ./start.sh
#  兼容: Ubuntu 18.04+ / Debian 10+ / CentOS 7+ / macOS 12+
# ============================================================
set -e
cd "$(dirname "$0")"

echo "============================================"
echo "  合同归档管理系统 v1.5"
echo "============================================"
echo ""

# -------------------- 第1步：释放8000端口 --------------------
echo "[1/5] 释放8000端口..."
PID=$(lsof -ti:8000 2>/dev/null || true)
if [ -n "$PID" ]; then
    echo "  - 终止占用进程 PID: $PID"
    kill "$PID" 2>/dev/null || true
    sleep 1
    # 如果还没死，强杀
    kill -9 "$PID" 2>/dev/null || true
    sleep 1
    echo "  - 端口已释放"
else
    echo "  - 端口空闲，无需释放"
fi

# -------------------- 第2步：清理缓存 --------------------
echo ""
echo "[2/5] 清理Python缓存..."
find backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find backend -type f -name "*.pyc" -delete 2>/dev/null || true
echo "  - 缓存清理完成"

# -------------------- 第3步：验证环境 --------------------
echo ""
echo "[3/5] 验证运行环境..."

VENV_PYTHON="backend/venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    echo "  [错误] 虚拟环境不存在: $VENV_PYTHON"
    echo "  [提示] 请先运行一键部署: ./deploy.sh"
    exit 1
fi
echo "  - 虚拟环境: OK"

if [ ! -f "backend/app/main.py" ]; then
    echo "  [错误] 未找到后端入口: backend/app/main.py"
    exit 1
fi
echo "  - 后端主程序: OK"

if [ ! -f "frontend/dist/app.html" ]; then
    echo "  [错误] 前端构建产物缺失: frontend/dist/app.html"
    echo "  [提示] 请先构建前端: cd frontend && npm install && npx vite build"
    exit 1
fi
echo "  - 前端构建产物: OK"

# -------------------- 第4步：启动后端 --------------------
echo ""
echo "[4/5] 启动后端服务..."

cd backend

# 检查 .env 是否存在，不存在则从模板生成
if [ ! -f ".env" ]; then
    if [ -f "../.env.example" ]; then
        echo "  - 从 .env.example 生成 .env"
        cp "../.env.example" ".env"
        # 生成随机 SECRET_KEY
        NEW_KEY=$("$VENV_PYTHON" -c "import secrets; print(secrets.token_hex(32))")
        sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$NEW_KEY/" ".env" 2>/dev/null || true
        echo "  - 已自动生成 SECRET_KEY"
    else
        echo "  [警告] 未找到 .env.example，将使用默认配置"
    fi
fi

"$VENV_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

echo "  - 后端已启动 (PID: $BACKEND_PID)"

# -------------------- 第5步：健康检查 --------------------
echo ""
echo "[5/5] 等待服务就绪..."
HEALTHY=0
for i in $(seq 1 20); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        HEALTHY=1
        echo "  - 服务就绪！(尝试 $i 次)"
        break
    fi
    echo "  - 等待中... $i/20"
    sleep 2
done

if [ "$HEALTHY" -eq 0 ]; then
    echo ""
    echo "============================================"
    echo "  [失败] 服务启动超时！"
    echo ""
    echo "  可能原因:"
    echo "  1. 查看终端上的红色报错信息"
    echo "  2. 端口8000被其他程序占用"
    echo "  3. Python依赖缺失，运行: cd backend && source venv/bin/activate && pip install -r requirements.txt"
    echo "============================================"
    exit 1
fi

# -------------------- 打开浏览器(可选) --------------------
echo ""
echo "============================================"
echo "  启动成功！"
echo "  地址: http://localhost:8000"
echo "  进程ID: $BACKEND_PID"
echo "  停止服务: ./stop.sh"
echo "  默认账号: admin / admin123 (请立即修改)"
echo "============================================"
echo ""

# 尝试打开浏览器
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8000 2>/dev/null &
elif command -v open &> /dev/null; then
    open http://localhost:8000 2>/dev/null &
fi

# 前台等待（Ctrl+C 停止）
wait $BACKEND_PID
