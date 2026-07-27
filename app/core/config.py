import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "access_token")
AUTH_COOKIE_MAX_AGE_SECONDS = int(os.getenv("AUTH_COOKIE_MAX_AGE_SECONDS", str(12 * 60 * 60)))
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "true").lower() == "true"
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "none")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_AGENT_MODEL = os.getenv("GEMINI_AGENT_MODEL", "gemini-3.6-flash")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
GEMINI_EMBEDDING_DIMENSIONS = int(os.getenv("GEMINI_EMBEDDING_DIMENSIONS", "768"))

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
