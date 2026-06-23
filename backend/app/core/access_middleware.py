"""
访问日志中间件
自动记录所有 API 请求（含响应状态、耗时、IP）
"""
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging_config import mask_sensitive


class AccessLogMiddleware(BaseHTTPMiddleware):
    """记录所有 HTTP 请求的访问日志"""

    async def dispatch(self, request: Request, call_next):
        access_logger = logging.getLogger("access")
        start_time = time.time()

        # 获取客户端 IP（考虑代理）
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        # 构建请求信息
        request_info = {
            "method": request.method,
            "path": request.url.path,
            "query": str(request.url.query) if request.url.query else None,
            "client_ip": client_ip,
            "user_agent": request.headers.get("User-Agent", "")[:200],
        }

        # 执行请求
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # 记录日志
        log_entry = {
            **request_info,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
        access_logger.info(log_entry)

        return response
