"""
认证 API
处理登录、注册、获取用户信息、登录失败锁定
"""
import logging
import time as _time
from collections import defaultdict as _defaultdict
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import timedelta, datetime

from app.core.database import get_db
from app.core.config import settings
from app.core.security import (
    verify_password, get_password_hash, create_access_token, get_current_user
)
from app.models.database import User, UserRole, Contract
from app.schemas.auth import Token, UserCreate, UserResponse, UserLogin


router = APIRouter(prefix="/api/auth", tags=["认证"])

# 登录失败锁定配置
MAX_FAILED_ATTEMPTS = 9  # 连续失败9次后锁定
LOCK_DURATION_MINUTES = 30  # 锁定30分钟

# ===== 登录端点专用速率限制（独立于全局限流，防暴力破解）=====
_LOGIN_RATE_LIMIT = 10        # 每分钟每IP最多10次登录尝试
_LOGIN_RATE_WINDOW = 60.0     # 时间窗口（秒）
_login_attempts: Dict[str, List[float]] = _defaultdict(list)


def _check_login_rate(ip: str) -> bool:
    """返回 True 表示触发限流（超过登录频率限制）"""
    now = _time.time()
    # 清理过期记录
    _login_attempts[ip] = [t for t in _login_attempts.get(ip, []) if now - t < _LOGIN_RATE_WINDOW]
    if len(_login_attempts[ip]) >= _LOGIN_RATE_LIMIT:
        return True
    _login_attempts[ip].append(now)
    return False


audit_logger = logging.getLogger("audit")


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    用户登录（JSON 格式）
    输入 {"username": "...", "password": "..."}，返回 JWT Token

    安全机制：
    - 连续输入密码错误9次后，账户被锁定30分钟
    - 锁定期间无论密码是否正确都无法登录
    - 登录成功后失败计数清零
    """
    # 登录端点专用速率限制（独立于全局限流，基于直连IP不可伪造）
    client_ip = request.client.host if request.client else "unknown"
    if _check_login_rate(client_ip):
        audit_logger.warning({
            "action": "LOGIN_RATE_LIMITED",
            "ip": client_ip,
        })
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试过于频繁，请1分钟后再试",
            headers={"Retry-After": "60"},
        )

    user = db.query(User).filter(User.username == login_data.username).first()

    # 用户不存在
    if not user:
        audit_logger.warning({
            "action": "LOGIN_FAILED",
            "username": login_data.username,
            "reason": "user_not_found",
            "ip": request.client.host if request.client else "unknown",
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查账户是否被锁定
    if user.locked_until and user.locked_until > datetime.now():
        remaining_minutes = int((user.locked_until - datetime.now()).total_seconds() / 60)
        audit_logger.warning({
            "action": "LOGIN_BLOCKED",
            "username": login_data.username,
            "reason": "account_locked",
            "remaining_minutes": remaining_minutes,
            "ip": request.client.host if request.client else "unknown",
        })
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"账户已被锁定，请 {remaining_minutes} 分钟后再试",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 密码错误
    if not verify_password(login_data.password, user.password_hash):
        # 增加失败计数
        user.failed_attempts += 1

        # 检查是否达到锁定阈值
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now() + timedelta(minutes=LOCK_DURATION_MINUTES)
            db.commit()
            audit_logger.warning({
                "action": "LOGIN_LOCKED",
                "username": login_data.username,
                "failed_attempts": user.failed_attempts,
                "locked_minutes": LOCK_DURATION_MINUTES,
                "ip": request.client.host if request.client else "unknown",
            })
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"密码连续错误 {MAX_FAILED_ATTEMPTS} 次，账户已被锁定 {LOCK_DURATION_MINUTES} 分钟",
                headers={"WWW-Authenticate": "Bearer"},
            )

        remaining_attempts = MAX_FAILED_ATTEMPTS - user.failed_attempts
        db.commit()
        audit_logger.warning({
            "action": "LOGIN_FAILED",
            "username": login_data.username,
            "reason": "wrong_password",
            "remaining_attempts": remaining_attempts,
            "ip": request.client.host if request.client else "unknown",
        })

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"用户名或密码错误，剩余 {remaining_attempts} 次尝试机会",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 密码正确：登录成功
    # 重置失败计数
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()

    # 检查账户是否被禁用
    if not user.is_active:
        audit_logger.warning({
            "action": "LOGIN_DENIED",
            "username": login_data.username,
            "reason": "account_disabled",
            "ip": request.client.host if request.client else "unknown",
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已被禁用，请联系管理员"
        )

    # 创建访问令牌
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    audit_logger.info({
        "action": "LOGIN_SUCCESS",
        "username": login_data.username,
        "user_id": user.id,
        "role": user.role.value,
        "ip": request.client.host if request.client else "unknown",
    })

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    注册新用户（仅管理员可操作）
    """
    # 检查是否为管理员
    if current_user.role != UserRole.ADMIN:
        audit_logger.warning({
            "action": "REGISTER_DENIED",
            "operator": current_user.username,
            "target_username": user_data.username,
            "reason": "not_admin",
            "ip": request.client.host if request.client else "unknown",
        })
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以创建用户"
        )
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    # 创建新用户
    new_user = User(
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        role=user_data.role or UserRole.USER
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    audit_logger.info({
        "action": "USER_CREATED",
        "operator": current_user.username,
        "new_username": user_data.username,
        "role": (user_data.role or UserRole.USER).value,
        "ip": request.client.host if request.client else "unknown",
    })

    return new_user


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return current_user


@router.post("/unlock/{user_id}")
async def unlock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    管理员手动解锁用户账户
    """
    # 检查是否为管理员
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以解锁账户"
        )

    # 获取目标用户
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 解锁账户
    target_user.failed_attempts = 0
    target_user.locked_until = None
    db.commit()

    return {"message": f"用户 {target_user.username} 已解锁"}


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有用户列表（仅管理员）"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以查看用户列表"
        )
    users = db.query(User).all()
    return users


@router.put("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    冻结/解冻用户账号（仅管理员）
    冻结后用户无法登录，但数据保留
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以管理用户状态"
        )

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 不能冻结自己
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能冻结自己的账号"
        )

    target_user.is_active = not target_user.is_active
    db.commit()

    action = "解冻" if target_user.is_active else "冻结"
    audit_logger.warning({
        "action": "USER_STATUS_CHANGED",
        "target_user": target_user.username,
        "target_id": target_user.id,
        "new_status": "active" if target_user.is_active else "frozen",
        "operator": current_user.username,
        "ip": request.client.host if request.client else "unknown",
    })

    return {
        "message": f"用户 {target_user.username} 已{action}",
        "is_active": target_user.is_active
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除用户（仅管理员）
    删除用户不会影响该用户创建的合同数据
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以删除用户"
        )

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 不能删除自己
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账号"
        )

    # 检查该用户是否有合同
    contract_count = db.query(Contract).filter(Contract.created_by == user_id).count()

    deleted_username = target_user.username

    # 将该用户的所有合同转交给当前管理员（保留数据）
    db.query(Contract).filter(Contract.created_by == user_id).update(
        {Contract.created_by: current_user.id}
    )

    # 删除用户
    db.delete(target_user)
    db.commit()

    audit_logger.warning({
        "action": "USER_DELETED",
        "target_user": deleted_username,
        "target_id": user_id,
        "contracts_preserved": contract_count,
        "operator": current_user.username,
        "ip": request.client.host if request.client else "unknown",
    })

    return {
        "message": f"用户 {deleted_username} 已删除",
        "contracts_preserved": contract_count
    }


@router.put("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    request: Request,
    password_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    管理员重置用户密码（仅管理员可操作）
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以重置密码"
        )

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    new_password = password_data.get("password", "")
    if not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码不能为空"
        )

    # 密码复杂度校验（与注册时一致）
    import re
    if len(new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码长度不能少于8位")
    if not re.search(r"[A-Z]", new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码必须包含至少一个大写字母")
    if not re.search(r"[a-z]", new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码必须包含至少一个小写字母")
    if not re.search(r"\d", new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码必须包含至少一个数字")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码必须包含至少一个特殊符号")

    target_user.password_hash = get_password_hash(new_password)
    db.commit()

    audit_logger.warning({
        "action": "PASSWORD_RESET",
        "target_user": target_user.username,
        "target_id": target_user.id,
        "operator": current_user.username,
        "ip": request.client.host if request.client else "unknown",
    })

    return {"message": f"用户 {target_user.username} 的密码已重置"}


@router.get("/lock-status/{username}")
async def get_lock_status(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询账户锁定状态（需登录认证，防止用户名枚举攻击）
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return {"locked": False}

    if user.locked_until and user.locked_until > datetime.now():
        remaining_minutes = int((user.locked_until - datetime.now()).total_seconds() / 60)
        return {
            "locked": True,
            "remaining_minutes": remaining_minutes
        }

    return {"locked": False}
