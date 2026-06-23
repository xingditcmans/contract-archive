"""
核心配置文件
这里存放所有可配置的参数，比如数据库连接信息、密钥等
"""
from pydantic_settings import BaseSettings
from typing import List
import os
import secrets


class Settings(BaseSettings):
    """应用配置类"""

    # 应用基本信息
    APP_NAME: str = "合同归档管理系统"
    APP_VERSION: str = "1.0.1"
    DEBUG: bool = True

    # ========== 安全关键配置 ==========
    
    # JWT 认证密钥
    # ⚠️ 生产环境必须通过环境变量设置，不能使用默认值！
    SECRET_KEY: str = ""
    
    # 环境标识（development / production）
    ENVIRONMENT: str = "development"
    
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # Token 24小时有效

    # ========== 数据库配置 ==========
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./data/contracts.db"
    )

    # ========== 文件上传配置 ==========
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 单文件最大 50MB
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"]

    # ========== CORS 配置 ==========
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # ========== 安全配置 ==========
    # 请求限流：每分钟最多请求次数（None=不限制）
    RATE_LIMIT_PER_MINUTE: int = 300

    # 受信任的反向代理 IP 列表（只有这些 IP 的 X-Forwarded-For 头会被信任）
    # 防止攻击者伪造 XFF 头绕过限流
    # 生产环境部署在 nginx 后时，改为 nginx 所在 IP（通常是 docker 网关或 127.0.0.1）
    TRUSTED_PROXY_IPS: List[str] = ["127.0.0.1", "::1"]
    
    # 允许访问API文档（生产环境建议关闭）
    ALLOW_API_DOCS: bool = True

    # ========== AI 识别配置（可选） ==========
    # 默认通过 .env 初始化，也可通过管理界面实时修改（保存到 data/ai_config.json）
    AI_ENABLED: bool = False
    AI_PROVIDER: str = ""
    AI_API_URL: str = ""
    AI_API_KEY: str = ""
    AI_MODEL: str = ""
    AI_MAX_TOKENS: int = 1024
    AI_TEMPERATURE: float = 0.1
    AI_TIMEOUT_SECONDS: int = 60
    AI_FALLBACK_ONLY: bool = True  # True=仅当正则识别不全时调用AI

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._validate_security()
    
    def _validate_security(self):
        """安全检查"""
        # 生产环境必须设置SECRET_KEY
        if self.ENVIRONMENT == "production":
            if not self.SECRET_KEY or self.SECRET_KEY == "":
                raise ValueError(
                    "⚠️  生产环境必须设置 SECRET_KEY 环境变量！\n"
                    "   生成方法：python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError("⚠️  SECRET_KEY 长度至少需要 32 个字符！")
        else:
            # 开发环境自动生成随机密钥
            if not self.SECRET_KEY:
                self.SECRET_KEY = secrets.token_hex(32)
                # 开发模式自动生成临时密钥
                print(f"[安全] 开发模式：自动生成临时 SECRET_KEY (长度={len(self.SECRET_KEY)})")

    @property
    def is_production(self) -> bool:
        """是否生产环境"""
        return self.ENVIRONMENT == "production"

    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建配置实例
settings = Settings()
