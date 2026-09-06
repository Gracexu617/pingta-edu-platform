from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AccessPasswordMiddleware(BaseHTTPMiddleware):
    """Simple shared-password protection for the first private public release."""

    _PUBLIC_PATHS = {"/health"}

    def __init__(self, app, settings: Settings) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._password = settings.app_access_password.strip()

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        is_public_request = request.method == "OPTIONS" or request.url.path in self._PUBLIC_PATHS
        if not self._password or is_public_request:
            return await call_next(request)
        provided = request.headers.get("X-App-Password", "").strip()
        if provided != self._password:
            return JSONResponse({"detail": "访问密码错误或缺失"}, status_code=401)
        return await call_next(request)
