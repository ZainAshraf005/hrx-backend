import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt


ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def _secret_key() -> str:
    secret = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET_KEY")
    if not secret:
        secret = "dev-secret-change-me"
    return secret


def normalize_email(email: str) -> str:
    return email.strip().lower()


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    return _hash_secret(otp)


def verify_otp(otp: str, otp_hash: str) -> bool:
    if not otp_hash:
        return False
    return _verify_secret(otp, otp_hash)


def hash_password(password: str) -> str:
    return _hash_secret(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return _verify_secret(password, password_hash)


def create_signed_token(payload: dict, expires_delta: timedelta) -> str:
    token_payload = payload.copy()
    token_payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(token_payload, _secret_key(), algorithm=ALGORITHM)


def decode_signed_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])
    except JWTError:
        return None


def _hash_secret(secret: str) -> str:
    return bcrypt.hashpw(_bcrypt_input(secret), bcrypt.gensalt()).decode("utf-8")


def _verify_secret(secret: str, secret_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_bcrypt_input(secret), secret_hash.encode("utf-8"))
    except ValueError:
        return False


def _bcrypt_input(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()
