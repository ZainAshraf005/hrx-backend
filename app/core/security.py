from datetime import timedelta, datetime, UTC
from jose import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def hash_password(password: str):
    return password_hash.hash(password)


def verify_password(password, hashed):
    return password_hash.verify(password, hashed)


def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.now(tz=UTC) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm='HS256'
    )
