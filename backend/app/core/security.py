from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__type="ID",
    argon2__time_cost=3,
    argon2__memory_cost=65536,  # ~64 MB
    argon2__parallelism=2,
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _jwt_keys_and_alg() -> Tuple[str, str]:
    secret = getattr(settings, "JWT_SECRET", None)

    if secret:
        alg = getattr(settings, "JWT_ALG", "HS256")
        return secret, alg
    raise RuntimeError("Brak konfiguracji JWT: ustaw JWT_PRIVATE_KEY/JWT_PUBLIC_KEY lub JWT_SECRET.")


def create_access_token(
        subject: str,
        *,
        expires_delta: Optional[timedelta] = None
) -> str:
    now = now_utc()
    exp = now + (expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MIN))
    iss = getattr(settings, "JWT_ISSUER", None)

    payload = {
        "sub": subject,
        "iss": iss,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": __import__("secrets").token_urlsafe(16),
    }

    signing_key, alg = _jwt_keys_and_alg()
    return jwt.encode(payload, signing_key, algorithm=alg)


def decode_access_token(token: str) -> Optional[Tuple[str, str]]:
    try:
        verify_key, alg = _jwt_keys_and_alg()
        iss = getattr(settings, "JWT_ISSUER", None)

        payload = jwt.decode(
            token,
            verify_key,
            algorithms=[alg],
            issuer=iss,
            options={
                "require_sub": True,
                "require_iat": True,
                "require_exp": True,
            },
        )
        return str(payload.get("sub")), str(payload.get("exp"))
    except JWTError:
        return None

def create_totp_setup_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode = {
        "sub": username,
        "exp": expire,
        "type": "totp_setup"
    }
    signing_key, alg = _jwt_keys_and_alg()
    return jwt.encode(to_encode, signing_key, algorithm=alg)
