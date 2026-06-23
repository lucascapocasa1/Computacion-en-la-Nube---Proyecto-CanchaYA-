"""
schemas/schemas.py — Validación de requests y serialización de responses.
"""

from datetime import date, time, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator
from ..models.models import TipoCancha, EstadoPago, TipoPago, RolUsuario


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
    precio_original: Optional[float] = None
    precio_descuento: Optional[float] = None
    descuento_porcentaje: Optional[int] = None
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
    tipo_pago: TipoPago
    monto_pagado: Optional[float] = None
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


# ── Descuentos ─────────────────────────────────────────────────────────────────

class DescuentoCreate(BaseModel):
    hora_desde: str  # HH:MM
    hora_hasta: str  # HH:MM
    porcentaje: int  # 10, 15, 20

    @field_validator("porcentaje")
    @classmethod
    def porcentaje_valido(cls, v: int) -> int:
        if v not in (10, 15, 20):
            raise ValueError("El porcentaje debe ser 10, 15 o 20")
        return v


class DescuentoResponse(BaseModel):
    id: int
    cancha_id: int
    hora_desde: str
    hora_hasta: str
    porcentaje: int
    activo: bool
    model_config = {"from_attributes": True}


# ── Precio cancha ──────────────────────────────────────────────────────────────

class PrecioUpdate(BaseModel):
    precio_hora: float

    @field_validator("precio_hora")
    @classmethod
    def precio_valido(cls, v: float) -> float:
        if v < 1000:
            raise ValueError("El precio mínimo es $1.000")
        if v > 100000:
            raise ValueError("El precio máximo es $100.000")
        return v


# ── Genérico ──────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
