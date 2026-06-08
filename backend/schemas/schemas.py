"""
schemas/schemas.py — Validación de requests y serialización de responses.
"""

from datetime import date, time, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator
from ..models.models import TipoCancha, EstadoPago, RolUsuario


# ── Cancha ──────────────────────────────────────────────────────────────────

class CanchaResponse(BaseModel):
    id: int
    nombre: str
    tipo: TipoCancha
    precio_hora: float
    activa: bool
    model_config = {"from_attributes": True}


# ── Turno ────────────────────────────────────────────────────────────────────

class TurnoResponse(BaseModel):
    id: int
    cancha_id: int
    fecha: date
    hora_inicio: time
    hora_fin: time
    disponible: bool
    cancha: CanchaResponse
    model_config = {"from_attributes": True}


# ── Usuario ──────────────────────────────────────────────────────────────────

class UsuarioCreate(BaseModel):
    nombre: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_minimo(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")
        return v

    @field_validator("nombre")
    @classmethod
    def nombre_no_vacio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre no puede estar vacío")
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UsuarioResponse(BaseModel):
    id: int
    nombre: str
    email: str
    rol: RolUsuario
    cancha_id: Optional[int]
    created_at: datetime
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse


# ── Ficha (fidelidad) ────────────────────────────────────────────────────────

class FichaResponse(BaseModel):
    cancha_id: int
    cancha_nombre: str
    fichas_acumuladas: int
    fichas_canjeadas: int
    fichas_disponibles: int
    puede_canjear: bool  # True si fichas_disponibles >= 10


# ── Reserva ──────────────────────────────────────────────────────────────────

class ReservaCreate(BaseModel):
    turno_id: int
    nombre_cliente: str
    email_cliente: EmailStr
    telefono_cliente: Optional[str] = None
    # Si el usuario está logueado, se puede pasar su ID para asociar la reserva
    usuario_id: Optional[int] = None

    @field_validator("nombre_cliente")
    @classmethod
    def nombre_no_vacio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre no puede estar vacío")
        return v.strip()


class ReservaResponse(BaseModel):
    id: int
    turno_id: int
    usuario_id: Optional[int]
    nombre_cliente: str
    email_cliente: str
    telefono_cliente: Optional[str]
    estado_pago: EstadoPago
    mp_preference_id: Optional[str]
    canje_fichas: bool
    created_at: datetime
    turno: TurnoResponse
    model_config = {"from_attributes": True}


# ── Pago ──────────────────────────────────────────────────────────────────────

class PagoConfirmacion(BaseModel):
    reserva_id: int
    status: str  # "approved" | "rejected"

    @field_validator("status")
    @classmethod
    def status_valido(cls, v: str) -> str:
        if v not in ("approved", "rejected"):
            raise ValueError("status debe ser 'approved' o 'rejected'")
        return v


# ── Canje de fichas ───────────────────────────────────────────────────────────

class CanjeRequest(BaseModel):
    turno_id: int
    usuario_id: int


# ── Genérico ──────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
