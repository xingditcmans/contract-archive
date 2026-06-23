"""
结构化日志系统
JSON格式、按天轮转、分离 access/error/audit 三类日志
"""
import logging
import json
import os
import re
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Optional


LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

SENSITIVE_FIELDS = {"password", "password_hash", "token", "secret", "authorization", "cookie"}


class JsonFormatter(logging.Formatter):
    """JSON 格式日志输出"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
        }

        if isinstance(record.msg, dict):
            log_entry.update(record.msg)
        else:
            log_entry["message"] = record.getMessage()

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class AccessLogFilter(logging.Filter):
    """只允许 access 日志通过"""

    def filter(self, record):
        return record.name == "access"


class AuditLogFilter(logging.Filter):
    """只允许 audit 日志通过"""

    def filter(self, record):
        return record.name == "audit"


def mask_sensitive(data: dict) -> dict:
    """脱敏处理：将敏感字段替换为 ***"""
    if not isinstance(data, dict):
        return data
    result = {}
    for k, v in data.items():
        if k.lower() in SENSITIVE_FIELDS:
            result[k] = "***"
        elif isinstance(v, dict):
            result[k] = mask_sensitive(v)
        elif isinstance(v, str) and len(v) > 50:
            # 超长字符串截断（可能是 base64 编码的文件等）
            result[k] = v[:50] + "..."
        else:
            result[k] = v
    return result


def _create_handler(filename: str, level: int = logging.INFO) -> TimedRotatingFileHandler:
    """创建按天轮转的文件处理器（保留30天）"""
    handler = TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, filename),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    return handler


def setup_logging():
    """初始化全局日志配置"""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 清除已有的处理器（防止重复添加）
    root_logger.handlers.clear()

    # access 日志：所有 HTTP 请求
    access_handler = _create_handler("access.log")
    access_handler.addFilter(AccessLogFilter())
    root_logger.addHandler(access_handler)

    # error 日志：所有 WARNING 及以上级别
    error_handler = _create_handler("error.log", logging.WARNING)
    root_logger.addHandler(error_handler)

    # audit 日志：操作审计
    audit_handler = _create_handler("audit.log")
    audit_handler.addFilter(AuditLogFilter())
    root_logger.addHandler(audit_handler)

    # 控制台输出（开发环境）
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"))
    root_logger.addHandler(console)

    # 创建专用 logger
    access_logger = logging.getLogger("access")
    audit_logger = logging.getLogger("audit")
    app_logger = logging.getLogger("app")

    return {
        "access": access_logger,
        "audit": audit_logger,
        "app": app_logger,
    }
