from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from app.api.organization_controller import router as organization_router
from app.api.email_test_controller import router as email_test_router
from app.api.auth_controller import router as auth_router
from app.api.employee_controller import router as employee_router


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

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# Routes registration
# -------------------------
app.include_router(organization_router, prefix="/api")
app.include_router(email_test_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(employee_router, prefix="/api")
