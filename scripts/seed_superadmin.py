import asyncio
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

import app.models
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password, normalize_email
from app.models.user.user_model import User


async def seed_superadmin() -> None:
    email = os.getenv("SUPERADMIN_EMAIL")
    password = os.getenv("SUPERADMIN_PASSWORD")

    if not email or not password:
        raise SystemExit("SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD are required")

    normalized_email = normalize_email(email)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                email=normalized_email,
                password_hash=hash_password(password),
                organization_id=None,
                role="superadmin",
                is_active=True,
                is_verified=True,
            )
            db.add(user)
        else:
            user.password_hash = hash_password(password)
            user.organization_id = None
            user.role = "superadmin"
            user.is_active = True
            user.is_verified = True

        await db.commit()

    print(f"Seeded superadmin: {normalized_email}")


if __name__ == "__main__":
    asyncio.run(seed_superadmin())
