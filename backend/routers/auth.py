"""
routers/auth.py
---------------
Endpoints de autenticación y registro.

POST /auth/registro  → crea cuenta de comprador
POST /auth/login     → devuelve JWT
GET  /auth/me        → devuelve datos del usuario logueado (requiere token)
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional

from ..db.database import get_db
from ..models.models import Usuario, RolUsuario
from ..schemas.schemas import UsuarioCreate, LoginRequest, UsuarioResponse, TokenResponse
from ..core.security import hash_password, verify_password, crear_token, decodificar_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["autenticación"])


def get_usuario_actual(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[Usuario]:
    """
    Dependencia reutilizable: extrae el usuario del JWT en el header Authorization.
    Devuelve None si no hay token (rutas opcionales).
    Lanza 401 si el token es inválido o el usuario no existe.
    """
    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Formato de token inválido. Usá: Bearer <token>")

    token = authorization.split(" ", 1)[1]
    payload = decodificar_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    usuario_id = payload.get("sub")
    if not usuario_id:
        raise HTTPException(status_code=401, detail="Token sin ID de usuario")

    usuario = db.query(Usuario).filter(Usuario.id == int(usuario_id)).first()
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")

    logger.debug(f"[AUTH] Usuario autenticado: {usuario.email} (id={usuario.id})")
    return usuario


def require_usuario(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Usuario:
    """Como get_usuario_actual pero lanza 401 si no hay token (ruta protegida)."""
    usuario = get_usuario_actual(authorization, db)
    if usuario is None:
        raise HTTPException(status_code=401, detail="Se requiere autenticación")
    return usuario


def require_duenio(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Usuario:
    """Solo permite acceso a usuarios con rol DUENIO."""
    usuario = require_usuario(authorization, db)
    if usuario.rol != RolUsuario.DUENIO:
        raise HTTPException(status_code=403, detail="Acceso solo para dueños de cancha")
    return usuario


# ── POST /auth/registro ────────────────────────────────────────────────────

@router.post("/registro", response_model=TokenResponse, status_code=201)
def registro(payload: UsuarioCreate, db: Session = Depends(get_db)):
    """
    Registra un nuevo comprador.
    Los dueños de cancha se crean desde el seed, no desde este endpoint.
    """
    logger.info(f"[AUTH] Intento de registro: {payload.email}")

    existing = db.query(Usuario).filter(Usuario.email == payload.email).first()
    if existing:
        logger.warning(f"[AUTH] Email ya registrado: {payload.email}")
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")

    usuario = Usuario(
        nombre=payload.nombre,
        email=payload.email,
        password_hash=hash_password(payload.password),
        rol=RolUsuario.COMPRADOR,
        cancha_id=None,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    token = crear_token({"sub": str(usuario.id), "rol": usuario.rol.value})
    logger.info(f"[AUTH] Usuario registrado: {usuario.email} (id={usuario.id})")

    return TokenResponse(access_token=token, usuario=usuario)


# ── POST /auth/login ───────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Login para compradores y dueños de cancha."""
    logger.info(f"[AUTH] Intento de login: {payload.email}")

    usuario = db.query(Usuario).filter(Usuario.email == payload.email).first()

    if not usuario:
        logger.warning(f"[AUTH] Email no encontrado: {payload.email}")
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    if not usuario.activo:
        raise HTTPException(status_code=401, detail="Cuenta desactivada")

    if not verify_password(payload.password, usuario.password_hash):
        logger.warning(f"[AUTH] Contraseña incorrecta para: {payload.email}")
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    token = crear_token({"sub": str(usuario.id), "rol": usuario.rol.value})
    logger.info(f"[AUTH] Login exitoso: {usuario.email} rol={usuario.rol}")

    return TokenResponse(access_token=token, usuario=usuario)


# ── GET /auth/me ───────────────────────────────────────────────────────────

@router.get("/me", response_model=UsuarioResponse)
def me(usuario: Usuario = Depends(require_usuario)):
    """Devuelve los datos del usuario autenticado."""
    return usuario
