"""
models/models.py — Modelos ORM completos

Tablas:
  canchas       → catálogo de canchas
  turnos        → slots de tiempo por cancha/día
  usuarios      → cuentas de compradores y dueños de cancha
  reservas      → una reserva = turno bloqueado temporalmente
  fichas        → sistema de fidelidad (1 reserva pagada = 1 ficha por cancha)

CAMBIO CLAVE vs versión anterior:
  El campo `turno.disponible` ahora solo se pone en False cuando el pago
  es APROBADO. Una reserva pendiente de pago NO bloquea el turno visualmente,
  aunque internamente existe para evitar condiciones de carrera.
  Si el pago se rechaza o expira, la reserva se elimina y el turno queda libre.
"""

from datetime import datetime, date, time
from sqlalchemy import (
    Integer, String, Boolean, Numeric,
    ForeignKey, DateTime, Date, Time,
    Enum as SAEnum, UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from ..db.database import Base


# ── Enums ──────────────────────────────────────────────────────────────────

class TipoCancha(str, enum.Enum):
    FUTBOL_5 = "futbol_5"
    FUTBOL_7 = "futbol_7"


class EstadoPago(str, enum.Enum):
    PENDIENTE = "pendiente"   # reserva creada, pago no iniciado o en proceso
    APROBADO  = "aprobado"    # pago confirmado por MP o mock → turno bloqueado
    RECHAZADO = "rechazado"   # pago rechazado/cancelado → turno vuelve a estar libre


class RolUsuario(str, enum.Enum):
    COMPRADOR = "comprador"   # puede reservar y ver historial propio
    DUENIO    = "duenio"      # puede ver ventas/reservas de SU cancha


# ── Cancha ─────────────────────────────────────────────────────────────────

class Cancha(Base):
    __tablename__ = "canchas"

    id: Mapped[int]   = mapped_column(Integer, primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo: Mapped[TipoCancha] = mapped_column(SAEnum(TipoCancha), nullable=False)
    precio_hora: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=5000)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)

    turnos:   Mapped[list["Turno"]]   = relationship("Turno",   back_populates="cancha")
    usuarios: Mapped[list["Usuario"]] = relationship("Usuario", back_populates="cancha")
    fichas:   Mapped[list["Ficha"]]   = relationship("Ficha",   back_populates="cancha")

    def __repr__(self):
        return f"<Cancha {self.nombre} ({self.tipo})>"


# ── Turno ──────────────────────────────────────────────────────────────────

class Turno(Base):
    __tablename__ = "turnos"

    id: Mapped[int]  = mapped_column(Integer, primary_key=True, index=True)
    cancha_id: Mapped[int] = mapped_column(Integer, ForeignKey("canchas.id"), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time]    = mapped_column(Time, nullable=False)
    # disponible=True  → libre para reservar
    # disponible=False → pago APROBADO, turno ocupado definitivamente
    disponible: Mapped[bool] = mapped_column(Boolean, default=True)

    cancha:  Mapped["Cancha"]  = relationship("Cancha", back_populates="turnos")
    reserva: Mapped["Reserva"] = relationship("Reserva", back_populates="turno", uselist=False)

    __table_args__ = (
        UniqueConstraint("cancha_id", "fecha", "hora_inicio", name="uq_turno_cancha_fecha_hora"),
    )

    def __repr__(self):
        return f"<Turno cancha={self.cancha_id} {self.fecha} {self.hora_inicio}>"


# ── Usuario ────────────────────────────────────────────────────────────────

class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int]   = mapped_column(Integer, primary_key=True, index=True)
    nombre: Mapped[str]  = mapped_column(String(150), nullable=False)
    email: Mapped[str]   = mapped_column(String(200), nullable=False, unique=True, index=True)
    # Contraseña hasheada con bcrypt (NUNCA se guarda en texto plano)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    rol: Mapped[RolUsuario] = mapped_column(SAEnum(RolUsuario), nullable=False)

    # Solo para dueños: referencia a SU cancha
    cancha_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("canchas.id"), nullable=True
    )

    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cancha:   Mapped["Cancha | None"] = relationship("Cancha", back_populates="usuarios")
    reservas: Mapped[list["Reserva"]] = relationship("Reserva", back_populates="usuario")
    fichas:   Mapped[list["Ficha"]]   = relationship("Ficha",   back_populates="usuario")

    def __repr__(self):
        return f"<Usuario {self.email} rol={self.rol}>"


# ── Reserva ────────────────────────────────────────────────────────────────

class Reserva(Base):
    __tablename__ = "reservas"

    id: Mapped[int]   = mapped_column(Integer, primary_key=True, index=True)
    turno_id: Mapped[int] = mapped_column(Integer, ForeignKey("turnos.id"), unique=True, nullable=False)

    # usuario_id es nullable: se puede reservar sin cuenta
    usuario_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("usuarios.id"), nullable=True
    )

    nombre_cliente: Mapped[str] = mapped_column(String(150), nullable=False)
    email_cliente:  Mapped[str] = mapped_column(String(200), nullable=False)
    telefono_cliente: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # PENDIENTE → no bloquea el turno
    # APROBADO  → turno.disponible = False
    # RECHAZADO → reserva se elimina, turno libre
    estado_pago: Mapped[EstadoPago] = mapped_column(
        SAEnum(EstadoPago), default=EstadoPago.PENDIENTE, nullable=False
    )
    mp_preference_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mp_payment_id:    Mapped[str | None] = mapped_column(String(200), nullable=True)

    # True si el turno fue canjeado con fichas (no pagó con dinero)
    canje_fichas: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    turno:   Mapped["Turno"]        = relationship("Turno",   back_populates="reserva")
    usuario: Mapped["Usuario | None"] = relationship("Usuario", back_populates="reservas")

    def __repr__(self):
        return f"<Reserva #{self.id} '{self.nombre_cliente}' pago={self.estado_pago}>"


# ── Ficha (fidelidad) ──────────────────────────────────────────────────────

class Ficha(Base):
    """
    Acumula 1 ficha por cada reserva PAGADA de un usuario en una cancha.
    Cuando fichas_disponibles llega a 10, el usuario puede canjear 1 turno gratis.
    El campo `fichas_canjeadas` lleva el acumulado histórico de canjes.
    """
    __tablename__ = "fichas"

    id: Mapped[int]   = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False)
    cancha_id:  Mapped[int] = mapped_column(Integer, ForeignKey("canchas.id"),  nullable=False)

    fichas_acumuladas:  Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fichas_canjeadas:   Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="fichas")
    cancha:  Mapped["Cancha"]  = relationship("Cancha",  back_populates="fichas")

    # Un usuario tiene un solo registro de fichas por cancha
    __table_args__ = (
        UniqueConstraint("usuario_id", "cancha_id", name="uq_ficha_usuario_cancha"),
    )

    @property
    def fichas_disponibles(self) -> int:
        """Fichas que puede usar ahora = acumuladas - canjeadas."""
        return self.fichas_acumuladas - self.fichas_canjeadas

    def __repr__(self):
        return (
            f"<Ficha user={self.usuario_id} cancha={self.cancha_id} "
            f"acum={self.fichas_acumuladas} canjeadas={self.fichas_canjeadas}>"
        )
