from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings


password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_token(
    user_id: int,
    role: str,
    token_type: str,
    expires_minutes: int,
) -> str:

    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=expires_minutes),
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_access_token(
    user_id: int,
    role: str,
) -> str:

    return create_token(
        user_id=user_id,
        role=role,
        token_type="access",
        expires_minutes=30,
    )


def create_refresh_token(
    user_id: int,
    role: str,
) -> str:

    return create_token(
        user_id=user_id,
        role=role,
        token_type="refresh",
        expires_minutes=60 * 24 * 7,
    )