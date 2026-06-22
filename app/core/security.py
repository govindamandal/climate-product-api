from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import jwt
import bcrypt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8")[:72], hashed_password.encode("utf-8"))


def create_access_token(*, subject: str, organization_id: str | None, role: str) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "org": organization_id,
        "role": role,
        "type": "access",
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token() -> tuple[str, str]:
    raw = f"{uuid4()}.{uuid4()}"
    return raw, hash_token(raw)


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
