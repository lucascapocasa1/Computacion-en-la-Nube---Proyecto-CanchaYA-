"""
core/security.py
----------------
Utilidades de seguridad: hash de contraseñas y JWT.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from passlib.context import CryptContext
from jose import JWTError, jwt

from .config import settings

logger = logging.getLogger(__name__)

# bcrypt para hashear contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Clave secreta para firmar JWT — en producción debe ser una var de entorno larga
SECRET_KEY = getattr(settings, "SECRET_KEY", "dev-secret-key-change-in-production-please")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def crear_token(data: dict, expire_hours: int = TOKEN_EXPIRE_HOURS) -> str:
    """Crea un JWT con expiración."""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decodificar_token(token: str) -> Optional[dict]:
    """Decodifica un JWT. Devuelve None si es inválido o expiró."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        logger.debug(f"Token inválido: {e}")
        return None
