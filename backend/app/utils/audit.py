"""
操作日志审计模块
记录关键操作的日志，用于安全审计和故障排查
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from functools import wraps
import json
import os

# 配置日志
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# 确保日志目录存在
LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)

# 文件处理器 - 写入审计日志
file_handler = logging.FileHandler(
    os.path.join(LOG_DIR, f"audit_{datetime.now().strftime('%Y%m')}.log"),
    encoding="utf-8"
)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
audit_logger.addHandler(file_handler)


class AuditLog:
    """审计日志类"""

    @staticmethod
    def log(
        action: str,
        username: str,
        status: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        记录操作日志
        
        Args:
            action: 操作类型（如 LOGIN, LOGOUT, CONTRACT_CREATE, FILE_UPLOAD 等）
            username: 用户名
            status: 操作状态（SUCCESS/FAILED/DENIED）
            details: 详细信息（字典）
            ip_address: IP地址
            user_agent: 用户代理
        """
        parts = [
            f"USER={username}",
            f"ACTION={action}",
            f"STATUS={status}",
        ]
        
        if details:
            # 敏感信息脱敏
            safe_details = AuditLog._sanitize(details)
            parts.append(f"DETAILS={json.dumps(safe_details, ensure_ascii=False)}")
        
        if ip_address:
            parts.append(f"IP={ip_address}")
            
        message = " | ".join(parts)
        
        if status == "FAILED":
            audit_logger.warning(message)
        elif status == "DENIED":
            audit_logger.error(message)
        else:
            audit_logger.info(message)

    @staticmethod
    def _sanitize(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        敏感信息脱敏
        不记录密码、token等敏感信息
        """
        sensitive_keys = [
            'password', 'password_hash', 'token', 'secret', 
            'key', 'authorization', 'cookie', 'session'
        ]
        
        result = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(s in key_lower for s in sensitive_keys):
                result[key] = "***脱敏***"
            elif isinstance(value, dict):
                result[key] = AuditLog._sanitize(value)
            else:
                result[key] = value
        
        return result

    @staticmethod
    def log_login(username: str, success: bool, ip: Optional[str] = None, reason: Optional[str] = None):
        """记录登录操作"""
        status = "SUCCESS" if success else "FAILED"
        details = {"reason": reason} if reason else None
        AuditLog.log("LOGIN", username, status, details, ip)

    @staticmethod
    def log_logout(username: str, ip: Optional[str] = None):
        """记录登出操作"""
        AuditLog.log("LOGOUT", username, "SUCCESS", ip_address=ip)

    @staticmethod
    def log_contract_create(username: str, contract_id: int, contract_no: str, ip: Optional[str] = None):
        """记录创建合同"""
        AuditLog.log(
            "CONTRACT_CREATE", username, "SUCCESS",
            {"contract_id": contract_id, "contract_no": contract_no},
            ip_address=ip
        )

    @staticmethod
    def log_contract_delete(username: str, contract_id: int, ip: Optional[str] = None):
        """记录删除合同"""
        AuditLog.log(
            "CONTRACT_DELETE", username, "SUCCESS",
            {"contract_id": contract_id},
            ip_address=ip
        )

    @staticmethod
    def log_file_upload(username: str, contract_id: int, filename: str, ip: Optional[str] = None):
        """记录文件上传"""
        AuditLog.log(
            "FILE_UPLOAD", username, "SUCCESS",
            {"contract_id": contract_id, "filename": filename},
            ip_address=ip
        )

    @staticmethod
    def log_access_denied(username: str, action: str, reason: str, ip: Optional[str] = None):
        """记录访问被拒绝"""
        AuditLog.log(
            action, username, "DENIED",
            {"reason": reason},
            ip_address=ip
        )


def audit(action: str):
    """
    审计装饰器
    自动记录被装饰函数的执行情况
    
    用法：
        @audit("CONTRACT_UPDATE")
        async def update_contract(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            username = kwargs.get('current_user')
            if username:
                username = getattr(username, 'username', str(username))
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                AuditLog.log(action, username or "UNKNOWN", "FAILED", {"error": str(e)})
                raise
        
        return wrapper
    return decorator
