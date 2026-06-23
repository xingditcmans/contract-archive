"""
数据库连接管理
负责创建数据库引擎和会话
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os

from app.core.config import settings


# 判断是否使用 SQLite
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite 需要特殊配置
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},  # SQLite 特殊参数
        echo=settings.DEBUG  # 打印 SQL 语句（调试用）
    )
else:
    # PostgreSQL / MySQL 等
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,  # 连接前检测
        echo=settings.DEBUG
    )


# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话的依赖函数
    用法：在 API 函数中传入 db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    初始化数据库
    创建所有表结构
    """
    from app.models.database import Base
    Base.metadata.create_all(bind=engine)
