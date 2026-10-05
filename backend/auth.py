"""Staff passcode."""

import hashlib
import hmac
import time

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.config import STAFF_PASSCODE

COOKIE = "sm_staff"
COOKIE_DAYS = 30
# Routes anyone may call: health check, login itself, Meta's webhook, and the
# demo buyer chat (those routes refuse to work unless DEMO_MODE is on)
PUBLIC = ("/api/health", "/api/login", "/api/logout", "/api/whatsapp/webhook", "/api/demo/chat", "/api/demo/photos")


def login_required():
    return bool(STAFF_PASSCODE)


def _token():
    return hmac.new(STAFF_PASSCODE.encode(), b"swatch-match-staff", hashlib.sha256).hexdigest()


def passcode_ok(passcode):
    ok = hmac.compare_digest(passcode.encode(), STAFF_PASSCODE.encode())
    if not ok:
        time.sleep(1)  # slow down guessing
    return ok


def set_cookie(response, request: Request):
    # Behind Hugging Face's proxy the original scheme is in x-forwarded-proto
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(
        COOKIE, _token(), max_age=COOKIE_DAYS * 86400, httponly=True, samesite="lax", secure=https
    )


async def guard(request: Request, call_next):
    path = request.url.path
    if login_required() and path.startswith("/api/") and not path.startswith(PUBLIC):
        cookie = request.cookies.get(COOKIE, "")
        if not hmac.compare_digest(cookie.encode(), _token().encode()):
            return JSONResponse({"detail": "Please enter the staff passcode."}, status_code=401)
    return await call_next(request)
