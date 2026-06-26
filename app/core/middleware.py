from collections import defaultdict, deque
from time import monotonic

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("x-content-type-options", "nosniff")
        response.headers.setdefault("x-frame-options", "DENY")
        response.headers.setdefault("referrer-policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("permissions-policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("cross-origin-opener-policy", "same-origin")
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers.setdefault("content-security-policy", "default-src 'none'; frame-ancestors 'none'")
        if request.url.scheme == "https":
            response.headers.setdefault("strict-transport-security", "max-age=31536000; includeSubDomains")
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, max_body_bytes: int) -> None:
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        try:
            body_size = int(content_length) if content_length else 0
        except ValueError:
            body_size = 0
        if body_size > self.max_body_bytes:
            return Response(
                content="Request body is too large",
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            )
        return await call_next(request)


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, requests_per_minute: int) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60
        self.attempts: dict[str, deque[float]] = defaultdict(deque)
        self.limited_paths = {
            "/api/v1/auth/login",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/accept-invite",
        }

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path in self.limited_paths:
            client_host = request.client.host if request.client else "unknown"
            key = f"{client_host}:{request.url.path}"
            now = monotonic()
            attempts = self.attempts[key]
            while attempts and now - attempts[0] > self.window_seconds:
                attempts.popleft()
            if len(attempts) >= self.requests_per_minute:
                return Response(
                    content="Too many authentication attempts",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={"retry-after": str(self.window_seconds)},
                )
            attempts.append(now)
        return await call_next(request)
