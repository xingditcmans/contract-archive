#!/bin/bash
# ============================================================
#  合同归档管理系统 — Linux 一键部署脚本
#  用法: chmod +x deploy.sh && ./deploy.sh
#  支持: Ubuntu 18.04+ / Debian 10+ / CentOS 7+
# ============================================================
set -e

# 兼容 root 和非 root 两种场景
# ECS 默认 root 登录，允许直接运行
if [ "$(id -u)" -eq 0 ]; then
    # root 用户：无需 sudo
    SUDO=""
    # 如果通过 sudo 运行，取原始用户名；否则就是 root
    RUN_USER="${SUDO_USER:-root}"
    echo "[信息] 以 root 用户运行，所有操作直接执行"
    echo "[信息] 服务将以用户 '$RUN_USER' 启动"
else
    SUDO="sudo"
    RUN_USER="$USER"
    echo "[信息] 以普通用户 '$RUN_USER' 运行，需要时自动 sudo"
fi

echo "============================================"
echo "  合同归档管理系统 — 一键部署"
echo "============================================"
echo ""

####################### 配置项 #######################
INSTALL_DIR="${INSTALL_DIR:-/opt/contract-archive}"
PORT="${PORT:-8000}"
DOMAIN="${DOMAIN:-}"  # 留空则不配置 nginx
SETUP_NGINX="${SETUP_NGINX:-no}"  # yes/no

####################### 检测系统 #######################
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    OS="unknown"
fi

echo "[INFO] 检测到系统: $OS"
echo "[INFO] 安装目录: $INSTALL_DIR"
echo "[INFO] 服务端口: $PORT"

####################### 系统依赖 #######################
echo ""
echo "[1/8] 安装系统依赖..."

install_system_deps() {
    case "$OS" in
        ubuntu|debian)
            $SUDO apt-get update -qq
            $SUDO apt-get install -y -qq python3 python3-venv python3-pip curl lsof tesseract-ocr tesseract-ocr-chi-sim > /dev/null 2>&1
            ;;
        centos|rhel|fedora|rocky|almalinux)
            if command -v dnf &> /dev/null; then
                $SUDO dnf install -y python3 python3-pip curl lsof tesseract tesseract-langpack-chi-sim > /dev/null 2>&1
            else
                $SUDO yum install -y python3 python3-pip curl lsof tesseract tesseract-langpack-chi-sim > /dev/null 2>&1
            fi
            ;;
        *)
            echo "  [警告] 未知系统，请手动安装: python3 python3-venv python3-pip tesseract-ocr"
            ;;
    esac
    echo "  - 系统依赖安装完成"
}

install_system_deps

# 检查 Python 版本
PYTHON_CMD="python3"
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "  [错误] 未找到 python3，请先安装 Python 3.10+"
    exit 1
fi

PYTHON_VER=$($PYTHON_CMD --version 2>&1 | grep -oP '\d+\.\d+')
echo "  - Python 版本: $PYTHON_VER"

####################### 创建目录 #######################
echo ""
echo "[2/8] 创建安装目录..."

$SUDO mkdir -p "$INSTALL_DIR"

# 获取项目源码目录（脚本所在目录）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

####################### 复制文件 #######################
echo ""
echo "[3/8] 复制项目文件..."

# 如果脚本就在目标目录中运行（zip 解压后直接部署），跳过复制
# 否则（git clone 或手动放置在不同位置）才复制文件
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    for DIR in backend frontend; do
        if [ -d "$SCRIPT_DIR/$DIR" ]; then
            $SUDO rsync -a --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' \
                --exclude='node_modules' --exclude='server.log' \
                "$SCRIPT_DIR/$DIR/" "$INSTALL_DIR/$DIR/" 2>/dev/null || \
            $SUDO cp -r "$SCRIPT_DIR/$DIR" "$INSTALL_DIR/"
        fi
    done

    # 复制脚本和配置
    for FILE in start.sh stop.sh .env.example Dockerfile docker-compose.yml .dockerignore; do
        if [ -f "$SCRIPT_DIR/$FILE" ]; then
            $SUDO cp "$SCRIPT_DIR/$FILE" "$INSTALL_DIR/"
        fi
    done
    echo "  - 文件从 $SCRIPT_DIR 复制到 $INSTALL_DIR"
else
    echo "  - 已在目标目录中运行，跳过复制"
fi

$SUDO chown -R "$RUN_USER:$RUN_USER" "$INSTALL_DIR" 2>/dev/null || true
echo "  - 文件复制完成"

####################### 创建虚拟环境 #######################
echo ""
echo "[4/8] 创建 Python 虚拟环境..."

cd "$INSTALL_DIR/backend"
if [ -d "venv" ]; then
    echo "  - 虚拟环境已存在，跳过"
else
    $PYTHON_CMD -m venv venv
    echo "  - 虚拟环境创建完成"
fi

####################### 安装 Python 依赖 #######################
echo ""
echo "[5/8] 安装 Python 依赖..."
VENV_PIP="$INSTALL_DIR/backend/venv/bin/pip"
$VENV_PIP install --upgrade pip -q
$VENV_PIP install -r "$INSTALL_DIR/backend/requirements.txt" -q
echo "  - 依赖安装完成"

####################### 配置环境变量 #######################
echo ""
echo "[6/8] 配置环境变量..."

if [ ! -f "$INSTALL_DIR/backend/.env" ]; then
    # 从模板生成
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/backend/.env"

    # 生成随机 SECRET_KEY
    NEW_KEY=$($INSTALL_DIR/backend/venv/bin/python -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$NEW_KEY/" "$INSTALL_DIR/backend/.env"
    echo "  - 已生成 SECRET_KEY (长度: 64)"

    # 设为生产模式
    sed -i "s/^ENVIRONMENT=.*/ENVIRONMENT=production/" "$INSTALL_DIR/backend/.env"
    echo "  - 已设为生产模式"

    # ⚠️ 关键修复：database.py 使用同步 create_engine，URL 不能含 +aiosqlite
    # 默认值已是 sqlite:/// 正确格式，但如果 .env.example 中有 +aiosqlite 则清理
    sed -i 's/+aiosqlite//' "$INSTALL_DIR/backend/.env"
    echo "  - DATABASE_URL 已清理（移除 +aiosqlite 确保同步兼容）"
else
    echo "  - .env 已存在，跳过"
fi

echo "  - 环境变量配置完成"

####################### 初始化目录 #######################
echo ""
echo "[7/8] 初始化数据和上传目录..."
mkdir -p "$INSTALL_DIR/backend/data" "$INSTALL_DIR/backend/uploads"
echo "  - 目录初始化完成"

####################### systemd + nginx(可选) #######################
echo ""
echo "[8/8] 配置 systemd 服务..."

# 生成 systemd 服务文件
cat > /tmp/contract-archive.service << EOF
[Unit]
Description=合同归档管理系统
After=network.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$INSTALL_DIR/backend
ExecStart=$INSTALL_DIR/backend/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=5
Environment=PATH=$INSTALL_DIR/backend/venv/bin:/usr/local/bin:/usr/bin:/bin

# 安全加固
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/contract-archive.service /etc/systemd/system/contract-archive.service
sudo systemctl daemon-reload
sudo systemctl enable contract-archive
sudo systemctl start contract-archive

echo "  - systemd 服务已配置并启动"

# 等待服务就绪
echo ""
echo "  等待服务就绪..."
for i in $(seq 1 15); do
    if curl -sf http://localhost:$PORT/health > /dev/null 2>&1; then
        echo "  - 服务就绪！"
        break
    fi
    sleep 2
done

####################### Nginx(可选) #######################
if [ "$SETUP_NGINX" = "yes" ] && [ -n "$DOMAIN" ]; then
    echo ""
    echo "  配置 Nginx 反向代理..."

    $SUDO apt-get install -y -qq nginx > /dev/null 2>&1 || true

    cat > /tmp/contract-archive-nginx.conf << NGINX_EOF
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX_EOF

    $SUDO mv /tmp/contract-archive-nginx.conf /etc/nginx/sites-available/contract-archive
    $SUDO ln -sf /etc/nginx/sites-available/contract-archive /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx
    echo "  - Nginx 配置完成: http://$DOMAIN"

    echo ""
    echo "  [提示] 建议使用 Let's Encrypt 配置 HTTPS："
    echo "    sudo apt install certbot python3-certbot-nginx"
    echo "    sudo certbot --nginx -d $DOMAIN"
fi

####################### 验证前端构建 #######################
echo ""
echo "  验证前端构建产物..."
if [ -f "$INSTALL_DIR/frontend/dist/index.html" ]; then
    echo "  - 前端构建文件: frontend/dist/ (正常)"
else
    echo "  [警告] frontend/dist/index.html 不存在！"
    echo "  请确认前端已构建："
    echo "    cd $INSTALL_DIR/frontend && npm install && npm run build"
fi

####################### 完成 #######################
echo ""
echo "============================================"
echo "  部署完成！"
echo ""
echo "  地址: http://localhost:$PORT"
echo "  默认账号: admin / admin123"
echo "  ⚠️  首次登录后请立即修改密码！"
echo ""
echo "  管理命令:"
echo "    sudo systemctl status contract-archive   # 查看状态"
echo "    sudo systemctl restart contract-archive  # 重启"
echo "    sudo systemctl stop contract-archive     # 停止"
echo "    journalctl -u contract-archive -f        # 查看日志"
echo "============================================"
