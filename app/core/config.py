import os
from typing import Literal, cast

from dotenv import load_dotenv

load_dotenv()


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} environment variable is required")
    return value


DATABASE_URL = _required_env("DATABASE_URL")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "access_token")
AUTH_COOKIE_MAX_AGE_SECONDS = int(os.getenv("AUTH_COOKIE_MAX_AGE_SECONDS", str(12 * 60 * 60)))
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "true").lower() == "true"
_auth_cookie_samesite = os.getenv("AUTH_COOKIE_SAMESITE", "none").lower()
if _auth_cookie_samesite not in {"lax", "strict", "none"}:
    raise RuntimeError("AUTH_COOKIE_SAMESITE must be one of: lax, strict, none")
AUTH_COOKIE_SAMESITE = cast(
    Literal["lax", "strict", "none"],
    _auth_cookie_samesite,
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
GEMINI_EMBEDDING_DIMENSIONS = int(os.getenv("GEMINI_EMBEDDING_DIMENSIONS", "768"))

XKIRO_API_KEY = os.getenv("XKIRO_API_KEY")
XKIRO_BASE_URL = os.getenv("XKIRO_BASE_URL", "https://api.xkiro.com/v1")
XKIRO_MODEL = os.getenv("XKIRO_MODEL", "mistralai/mistral-large-2512")

AI_AGENT_MAX_TOOL_ROUNDS = int(os.getenv("AI_AGENT_MAX_TOOL_ROUNDS", "8"))
AI_AGENT_MAX_RESULT_ROWS = int(os.getenv("AI_AGENT_MAX_RESULT_ROWS", "50"))
AI_ACTION_PROPOSAL_TTL_SECONDS = int(os.getenv("AI_ACTION_PROPOSAL_TTL_SECONDS", "600"))
AI_INDEX_WORKER_POLL_SECONDS = float(os.getenv("AI_INDEX_WORKER_POLL_SECONDS", "2"))
AI_INDEX_WORKER_MAX_ATTEMPTS = int(os.getenv("AI_INDEX_WORKER_MAX_ATTEMPTS", "5"))

RESUME_MAX_UPLOAD_BYTES = int(os.getenv("RESUME_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
RESUME_ALLOWED_EXTENSIONS = {
    extension.strip().lower()
    for extension in os.getenv("RESUME_ALLOWED_EXTENSIONS", "pdf,docx").split(",")
    if extension.strip()
}
