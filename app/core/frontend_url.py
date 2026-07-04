from typing import Optional
from urllib.parse import urlparse

from fastapi import Request

from app.core.config import FRONTEND_URL


def get_frontend_url_from_request(request: Request) -> str:
    for header_name in ("x-frontend-origin", "origin", "referer"):
        frontend_url = _normalize_origin(request.headers.get(header_name))
        if frontend_url:
            return frontend_url

    return FRONTEND_URL.rstrip("/")


def _normalize_origin(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
