"""
安全中间件
提供安全响应头、请求限流、IP限制等防护功能
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
import hashlib
import secrets
from collections import defaultdict
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    安全响应头中间件
    防止常见的Web攻击：
    - XSS（跨站脚本攻击）
    - 点击劫持
    - MIME类型嗅探
    - 强制使用HTTPS（生产环境）
    """

    async def dispatch(self, request: Request, call_next):
        # 生成 CSP nonce（每次请求唯一，防 XSS）
        nonce = secrets.token_hex(16)
        request.state.csp_nonce = nonce

        response = await call_next(request)

        # 安全响应头
        response.headers["X-Content-Type-Options"] = "nosniff"  # 禁止MIME嗅探
        response.headers["X-Frame-Options"] = "SAMEORIGIN"  # 允许同源iframe，阻止跨域嵌入
        response.headers["X-XSS-Protection"] = "1; mode=block"  # XSS过滤器
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        
        # 防止缓存敏感数据
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        # 内容安全策略（使用 nonce 替代 unsafe-inline，防 XSS）
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'nonce-{nonce}'; "
            f"img-src 'self' data:; "
            f"font-src 'self'; "
            f"connect-src 'self'; "
            f"frame-ancestors 'self';"
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    请求限流中间件
    防止DDoS攻击和暴力破解

    基于内存的简单限流，生产环境建议使用Redis
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        burst_size: int = 10
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size  # 允许的突发请求数
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.window = 60.0  # 时间窗口（秒）

    # 受信任的代理 IP（只有来自这些 IP 的请求才信任 XFF/X-Real-IP 头）
    # 默认只信任本地回环地址，防止攻击者伪造 XFF 绕过限流
    # 生产环境可通过 config.TRUSTED_PROXY_IPS 配置
    _TRUSTED_PROXIES = None

    @property
    def _trusted_proxies(self) -> set:
        if self._TRUSTED_PROXIES is None:
            from app.core.config import settings
            self._TRUSTED_PROXIES = set(settings.TRUSTED_PROXY_IPS)
        return self._TRUSTED_PROXIES

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP（考虑代理，但只信任已知代理）"""
        # 获取直连 IP（可能是代理服务器的 IP）
        direct_ip = request.client.host if request.client else None

        # 只有来自受信任代理的请求，才读取 X-Forwarded-For / X-Real-IP
        # 这防止了攻击者直接发送伪造的 XFF 头绕过限流
        if direct_ip and direct_ip in self._trusted_proxies:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()

            real_ip = request.headers.get("x-real-ip")
            if real_ip:
                return real_ip

        # 否则使用直连 IP
        return direct_ip or "unknown"

    def _cleanup_old_requests(self, ip: str):
        """清理过期的请求记录"""
        current_time = time.time()
        # 只保留60秒内的请求
        self.requests[ip] = [
            t for t in self.requests[ip]
            if current_time - t < self.window
        ]

    def _is_rate_limited(self, ip: str) -> Tuple[bool, int]:
        """
        检查是否超过限流阈值
        返回：(是否限流, 剩余请求数)
        """
        current_time = time.time()
        self._cleanup_old_requests(ip)

        # 获取最近60秒内的请求时间
        recent_requests = self.requests[ip]
        
        # 如果请求数超过限制
        if len(recent_requests) >= self.requests_per_minute:
            return True, 0
        
        # 记录这次请求
        self.requests[ip].append(current_time)
        
        remaining = self.requests_per_minute - len(self.requests)
        return False, max(0, remaining)

    # 本地回环地址（不受限流约束）
    _LOCAL_IPS = {"127.0.0.1", "::1", "localhost"}

    async def dispatch(self, request: Request, call_next):
        # 跳过健康检查和根路径
        if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        client_ip = self._get_client_ip(request)

        # 本地请求不限流（页面加载会同时产生大量 API 调用）
        if client_ip in self._LOCAL_IPS:
            return await call_next(request)
        
        # 检查是否限流
        is_limited, remaining = self._is_rate_limited(client_ip)
        
        if is_limited:
            logger.warning(f"⛔ IP {client_ip} 请求过于频繁，已限流")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "请求过于频繁，请稍后再试",
                    "error": "rate_limit_exceeded"
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0"
                }
            )

        response = await call_next(request)
        
        # 添加限流响应头
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response


class IPBlocklistMiddleware(BaseHTTPMiddleware):
    """
    IP黑名单中间件
    可以手动封禁恶意IP
    """

    def __init__(self, app: ASGIApp, blocked_ips: List[str] = None):
        super().__init__(app)
        self.blocked_ips: set = set(blocked_ips or [])

    def block_ip(self, ip: str):
        """添加IP到黑名单"""
        self.blocked_ips.add(ip)
        logger.warning(f"🚫 IP {ip} 已被加入黑名单")

    def unblock_ip(self, ip: str):
        """从黑名单移除IP"""
        self.blocked_ips.discard(ip)

    async def dispatch(self, request: Request, call_next):
        # 获取客户端IP
        client_ip = request.client.host if request.client else None
        
        if client_ip and client_ip in self.blocked_ips:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "访问被拒绝"}
            )

        return await call_next(request)
