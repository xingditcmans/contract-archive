"""
Pydantic 数据模型（请求/响应验证）
定义 API 输入输出的数据结构
"""
import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


# ==================== 认证相关 ====================
class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class Token(BaseModel):
    """登录返回的 Token"""
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    role: Optional[UserRole] = UserRole.USER

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """密码复杂度校验：至少8位，包含大小写字母、数字、特殊符号"""
        if len(v) < 8:
            raise ValueError("密码长度不能少于8位")
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含至少一个大写字母")
        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含至少一个小写字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含至少一个数字")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", v):
            raise ValueError("密码必须包含至少一个特殊符号（如 !@#$%^&*）")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """用户名仅允许字母、数字、下划线"""
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """登录请求（备用）"""
    username: str
    password: str
