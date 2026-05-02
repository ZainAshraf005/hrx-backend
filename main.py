from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.api.organization_controller import router as organization_router


# -------------------------
# Lifespan (replaces on_event)
# -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    print("🚀 HRX backend starting...")

    yield

    # shutdown
    print("🛑 HRX backend shutting down...")


# -------------------------
# App instance
# -------------------------
app = FastAPI(
    title="HRX API",
    version="0.1.0",
    lifespan=lifespan
)


# -------------------------
# Routes registration
# -------------------------
app.include_router(organization_router, prefix="/api")