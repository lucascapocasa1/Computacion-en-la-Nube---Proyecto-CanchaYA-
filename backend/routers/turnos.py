"""
routers/turnos.py
-----------------
Endpoints relacionados con canchas y disponibilidad de turnos.

GET /canchas             → lista todas las canchas activas
GET /turnos              → lista turnos disponibles (con filtros opcionales)
GET /turnos/{turno_id}   → detalle de un turno
"""

from datetime import date, datetime, timedelta
from genericpath import exists
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import exists, and_, or_

from ..db.database import get_db
from ..models.models import Cancha, Turno, Reserva, EstadoPago, Descuento
from ..schemas.schemas import CanchaResponse, TurnoResponse

router = APIRouter(tags=["canchas y turnos"])


# ---------------------------------------------------------------------------
# GET /canchas
# ---------------------------------------------------------------------------
@router.get("/canchas", response_model=list[CanchaResponse])
def listar_canchas(db: Session = Depends(get_db)):
    """Devuelve todas las canchas activas."""
    canchas = db.query(Cancha).filter(Cancha.activa == True).all()
    return canchas


# ---------------------------------------------------------------------------
# GET /turnos
# ---------------------------------------------------------------------------
@router.get("/turnos", response_model=list[TurnoResponse])
def listar_turnos(
    cancha_id: Optional[int] = Query(None, description="Filtrar por cancha"),
    fecha: Optional[date]    = Query(None, description="Filtrar por fecha (YYYY-MM-DD)"),
    solo_disponibles: bool   = Query(True,  description="Solo turnos sin reserva"),
    db: Session = Depends(get_db),
):
    """
    Devuelve turnos, con filtros opcionales.
    Por defecto muestra solo los disponibles de los próximos 7 días.
    """
    query = db.query(Turno).options(joinedload(Turno.cancha))

    # Filtro por cancha
    if cancha_id:
        query = query.filter(Turno.cancha_id == cancha_id)

    # Filtro por fecha; si no se especifica, muestra la semana siguiente
    if fecha:
        query = query.filter(Turno.fecha == fecha)
    else:
        hoy = date.today()
        query = query.filter(
            Turno.fecha >= hoy,
            Turno.fecha <= hoy + timedelta(days=7)
        )

    # No mostrar turnos cuya hora ya pasó (para hoy)
    ahora = datetime.now()
    query = query.filter(
        or_(
            Turno.fecha > ahora.date(),
            and_(
                Turno.fecha == ahora.date(),
                Turno.hora_inicio > ahora.time()
            )
        )
    )

    if solo_disponibles:
        query = query.filter(
            Turno.disponible == True,
            ~exists().where(
                and_(
                    Reserva.turno_id == Turno.id,
                    Reserva.estado_pago == EstadoPago.PENDIENTE
                )
            )
        )

    turnos = query.order_by(Turno.fecha, Turno.hora_inicio).all()

    # Agregar info de descuento a cada turno
    resultado = []
    for t in turnos:
        descuento_activo = (
            db.query(Descuento)
            .filter(
                Descuento.cancha_id == t.cancha_id,
                Descuento.activo == True,
                Descuento.hora_desde <= t.hora_inicio,
                Descuento.hora_hasta >= t.hora_inicio,
            )
            .first()
        )
        dct = t.__dict__.copy()
        precio_original = float(t.cancha.precio_hora)
        dct["precio_original"] = precio_original
        dct["precio_descuento"] = None
        dct["descuento_porcentaje"] = None

        if descuento_activo:
            pct = descuento_activo.porcentaje
            dct["precio_descuento"] = round(precio_original * (1 - pct / 100), 2)
            dct["descuento_porcentaje"] = pct

        resultado.append(TurnoResponse.model_validate(dct))

    return resultado


# ---------------------------------------------------------------------------
# GET /turnos/{turno_id}
# ---------------------------------------------------------------------------
@router.get("/turnos/{turno_id}", response_model=TurnoResponse)
def detalle_turno(turno_id: int, db: Session = Depends(get_db)):
    """Devuelve el detalle de un turno específico."""
    turno = (
        db.query(Turno)
        .options(joinedload(Turno.cancha))
        .filter(Turno.id == turno_id)
        .first()
    )
    if not turno:
        raise HTTPException(status_code=404, detail="Turno no encontrado")

    descuento_activo = (
        db.query(Descuento)
        .filter(
            Descuento.cancha_id == turno.cancha_id,
            Descuento.activo == True,
            Descuento.hora_desde <= turno.hora_inicio,
            Descuento.hora_hasta >= turno.hora_inicio,
        )
        .first()
    )
    dct = turno.__dict__.copy()
    precio_original = float(turno.cancha.precio_hora)
    dct["precio_original"] = precio_original
    dct["precio_descuento"] = None
    dct["descuento_porcentaje"] = None

    if descuento_activo:
        pct = descuento_activo.porcentaje
        dct["precio_descuento"] = round(precio_original * (1 - pct / 100), 2)
        dct["descuento_porcentaje"] = pct

    return TurnoResponse.model_validate(dct)
