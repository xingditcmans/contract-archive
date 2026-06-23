"""
合同归档管理系统 - FastAPI 后端
主入口文件
"""
import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import setup_logging
from app.core.access_middleware import AccessLogMiddleware
from app.core.security_middleware import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    IPBlocklistMiddleware
)
from app.api import auth, contracts, admin


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## 合同归档管理系统 API

### 功能模块
- 🔐 用户认证（登录、注册、权限管理）
- 📋 合同管理（增删改查、多条件搜索）
- 📎 附件管理（上传、下载、删除）
- 🔍 OCR 识别（PDF/图片文字提取）
- 📊 Excel 导出
- 🏢 我方公司管理

### 安全特性
- 🛡️ JWT认证 + Argon2密码哈希
- 🔒 登录失败锁定（防暴力破解）
- ⏱️ 请求限流（防DDoS）
- 🔐 安全响应头（防XSS、点击劫持）
- 📝 操作日志审计
""",
    docs_url="/api/docs" if not settings.is_production else None,  # 生产环境关闭
    redoc_url="/api/redoc" if not settings.is_production else None
)


# ==================== 安全中间件 ====================

# 1. 安全响应头（XSS防护、点击劫持防护等）
app.add_middleware(SecurityHeadersMiddleware)

# 2. 请求限流（每分钟60次，防止DDoS和暴力破解）
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
    burst_size=10
)

# 3. IP黑名单（可以动态管理）
ip_blocklist = IPBlocklistMiddleware(app)

# 4. 访问日志（记录所有 API 请求，必须在其他中间件之后以确保状态码正确）
app.add_middleware(AccessLogMiddleware)


# ==================== 跨域配置 ====================
# 根据环境调整CORS配置
if settings.is_production:
    # 生产环境：只允许配置的域名
    cors_origins = settings.CORS_ORIGINS
else:
    # 开发环境：允许更多
    cors_origins = [
        *settings.CORS_ORIGINS,
        "http://localhost:*",
        "http://127.0.0.1:*",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 全局异常处理（把 traceback 写入日志）====================
import traceback as _traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """把所有未捕获的 500 错误 traceback 写入 error.log"""
    tb = _traceback.format_exc()
    _err_logger = logging.getLogger("app.error")
    _err_logger.error(f"未捕获异常 [{request.method} {request.url.path}]: {type(exc).__name__}: {exc}\n{tb}")

    # 生产环境只返回通用错误消息，防止泄露内部异常类型和堆栈信息
    if settings.is_production:
        detail = "服务器内部错误，请联系管理员"
    else:
        detail = f"{type(exc).__name__}: {str(exc)}"

    return JSONResponse(
        status_code=500,
        content={"detail": detail}
    )


# ==================== 启动事件 ====================
@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    # 打印启动信息
    print("\n" + "="*50)
    print(f"[STARTUP] {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"  环境: {settings.ENVIRONMENT}")
    print(f"  安全模式: {'生产' if settings.is_production else '开发'}")
    print("="*50 + "\n")

    # 初始化结构化日志系统
    setup_logging()
    logging.getLogger("app").info({
        "event": "startup",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    })

    # 确保上传目录存在
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs("./data", exist_ok=True)

    # 初始化数据库
    init_db()

    # ---- 迁移：为旧数据库补充新字段 ----
    from app.core.database import engine as db_engine
    from sqlalchemy import text, inspect as sa_inspect
    with db_engine.connect() as conn:
        inspector = sa_inspect(db_engine)
        # 检查 contracts 表是否已有 status 列
        existing_cols = [col["name"] for col in inspector.get_columns("contracts")]
        if "status" not in existing_cols:
            conn.execute(text("ALTER TABLE contracts ADD COLUMN status VARCHAR(10) NOT NULL DEFAULT 'ACTIVE'"))
            conn.commit()
            print("[MIGRATE] contracts.status 列已添加")
    # ---- 迁移结束 ----

    # 创建默认管理员账号（仅当不存在时）
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.database import User, UserRole

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin:
            admin_user = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role=UserRole.ADMIN
            )
            db.add(admin_user)
            db.commit()
            print("[OK] 默认管理员已创建（初始密码见部署文档）")
            if settings.is_production:
                print("[WARN] 生产环境请立即修改默认密码！")
            else:
                print("[INFO] 开发环境默认密码: admin123")
    finally:
        db.close()


# ==================== 路由注册 ====================
app.include_router(auth.router)
app.include_router(contracts.router)
app.include_router(admin.router)


# ==================== 根路径（iframe 隔离外壳，焊死在代码中，绝不依赖前端构建） ====================
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """iframe 隔离外壳 — Vue 应用隔离在 iframe 内部，彻底杜绝窗口跳闪"""
    nonce = getattr(request.state, 'csp_nonce', '')
    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>合同归档管理系统</title>
  <style nonce="{nonce}">
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html, body {{ width: 100%; height: 100%; overflow: hidden; background: #f5f7fa; }}
    iframe {{ width: 100%; height: 100%; border: none; display: block; }}
  </style>
</head>
<body>
  <iframe src="/app.html" title="合同归档管理系统"></iframe>
</body>
</html>"""


# ==================== 前端静态文件（生产模式） ====================
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    # 挂载静态资源（JS/CSS/图片等）
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # 上传文件目录不再公开挂载（安全加固：附件只能通过认证 API 下载）
    # 下载路径：GET /api/contracts/{id}/attachments/{aid}/download
    # 预览路径：GET /api/contracts/{id}/attachments/{aid}/preview?token=xxx

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str, request: Request):
        """
        SPA 回退 — 所有非 API/静态的路径返回外壳 index.html
        iframe 外壳加载 /app.html（完整 Vue 应用），隔离窗口焦点
        
        架构：浏览器 → index.html(极简外壳) → iframe → app.html(Vue应用)
        这个外壳彻底杜绝了窗口跳闪问题
        """
        from fastapi.responses import JSONResponse

        # 跳过 API 路径
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "API 路径不存在"})

        # HTML 入口文件永不缓存（hash 化资源由 /assets/ 处理）
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }

        # 特殊 HTML 文件直接返回（如 app.html）
        if full_path.endswith(".html"):
            requested_file = os.path.join(FRONTEND_DIST, full_path.lstrip("/"))
            if os.path.isfile(requested_file):
                return FileResponse(requested_file, headers=headers)

        # 所有其他路径回退到 app.html（Vue 应用在 iframe 内处理路由）
        app_path = os.path.join(FRONTEND_DIST, "app.html")
        if os.path.isfile(app_path):
            return FileResponse(app_path, headers=headers)
        return JSONResponse(status_code=404, content={"detail": "页面不存在"})

    print(f"[OK] 前端静态文件已挂载: {FRONTEND_DIST}")
else:
    print(f"[WARN] 前端构建目录不存在: {FRONTEND_DIST}，请先执行 npm run build")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


# ==================== 运行说明 ====================
if __name__ == "__main__":
    import uvicorn
    
    # 根据环境调整日志级别
    log_level = "warning" if settings.is_production else "info"
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=not settings.is_production,
        log_level=log_level
    )
