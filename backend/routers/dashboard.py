"""
routers/dashboard.py — Panel exclusivo para dueños de cancha

Endpoints:
  GET /dashboard/resumen       → estadísticas globales de la cancha
  GET /dashboard/reservas      → lista completa con datos del cliente
  GET /dashboard/turnos-hoy    → timeline de hoy (libre/pendiente/pagado)
  GET /dashboard/proximos-dias → resumen de los próximos 7 días
"""

import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from ..db.database import get_db
from ..models.models import Reserva, Turno, Ficha, Cancha, EstadoPago, Usuario
from ..routers.auth import require_duenio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _get_turno_ids(db: Session, cancha_id: int) -> list[int]:
    """Devuelve los IDs de todos los turnos de una cancha."""
    rows = db.query(Turno.id).filter(Turno.cancha_id == cancha_id).all()
    return [r.id for r in rows]


# ── GET /dashboard/resumen ────────────────────────────────────────────────────

@router.get("/resumen")
def resumen_cancha(
    duenio: Usuario = Depends(require_duenio),
    db: Session = Depends(get_db),
):
    """
    Estadísticas globales de la cancha del dueño.
    Incluye: reservas por estado, ingresos totales, del día y mensuales.
    """
    logger.info(f"[DASHBOARD] Resumen solicitado por {duenio.email} — cancha {duenio.cancha_id}")

    if not duenio.cancha_id:
        raise HTTPException(status_code=400, detail="Tu cuenta no tiene cancha asignada")

    cancha = db.query(Cancha).filter(Cancha.id == duenio.cancha_id).first()
    if not cancha:
        raise HTTPException(status_code=404, detail="Cancha no encontrada")

    turno_ids = _get_turno_ids(db, duenio.cancha_id)
    if not turno_ids:
        return _resumen_vacio(duenio.cancha_id, cancha.nombre)

    reservas = (
        db.query(Reserva)
        .options(joinedload(Reserva.turno))
        .filter(Reserva.turno_id.in_(turno_ids))
        .all()
    )

    aprobadas_dinero = [r for r in reservas if r.estado_pago == EstadoPago.APROBADO and not r.canje_fichas]
    aprobadas_canje  = [r for r in reservas if r.estado_pago == EstadoPago.APROBADO and r.canje_fichas]
    pendientes       = [r for r in reservas if r.estado_pago == EstadoPago.PENDIENTE]

    precio = float(cancha.precio_hora)
    ingresos_reales    = len(aprobadas_dinero) * precio
    ingresos_potencial = len(pendientes) * precio

    # Ingresos del día
    hoy = date.today()
    ingresos_dia = db.query(func.count(Reserva.id)).join(Turno).filter(
        Turno.cancha_id == duenio.cancha_id,
        Turno.fecha == hoy,
        Reserva.estado_pago == EstadoPago.APROBADO,
        Reserva.canje_fichas == False,
    ).scalar() or 0
    ingresos_dia = ingresos_dia * precio

    # Ingresos del mes
    primer_dia_mes = hoy.replace(day=1)
    ingresos_mensuales = db.query(func.count(Reserva.id)).join(Turno).filter(
        Turno.cancha_id == duenio.cancha_id,
        Turno.fecha >= primer_dia_mes,
        Turno.fecha <= hoy,
        Reserva.estado_pago == EstadoPago.APROBADO,
        Reserva.canje_fichas == False,
    ).scalar() or 0
    ingresos_mensuales = ingresos_mensuales * precio

    # Turnos libres hoy
    libres_hoy = db.query(Turno).filter(
        Turno.cancha_id == duenio.cancha_id,
        Turno.fecha == hoy,
        Turno.disponible == True,
    ).count()

    resultado = {
        "cancha_id":           duenio.cancha_id,
        "cancha_nombre":       cancha.nombre,
        "reservas_aprobadas":  len(aprobadas_dinero),
        "reservas_canje":      len(aprobadas_canje),
        "reservas_pendientes": len(pendientes),
        "ingresos_reales":     ingresos_reales,
        "ingresos_potencial":  ingresos_potencial,
        "ingresos_dia":        ingresos_dia,
        "ingresos_mensuales":  ingresos_mensuales,
        "turnos_libres_hoy":   libres_hoy,
        "precio_hora":         precio,
    }
    logger.info(f"[DASHBOARD] Resumen cancha {duenio.cancha_id}: {resultado}")
    return resultado


def _resumen_vacio(cancha_id: int, nombre: str) -> dict:
    return {
        "cancha_id": cancha_id, "cancha_nombre": nombre,
        "reservas_aprobadas": 0, "reservas_canje": 0,
        "reservas_pendientes": 0, "ingresos_reales": 0,
        "ingresos_potencial": 0, "ingresos_dia": 0,
        "ingresos_mensuales": 0, "turnos_libres_hoy": 0,
        "precio_hora": 0,
    }


# ── GET /dashboard/reservas ───────────────────────────────────────────────────

@router.get("/reservas")
def reservas_cancha(
    fecha: Optional[date] = None,
    estado: Optional[str] = None,   # "pendiente" | "aprobado" | "rechazado"
    duenio: Usuario = Depends(require_duenio),
    db: Session = Depends(get_db),
):
    """
    Lista detallada de reservas: quién reservó, cuándo, qué turno y estado de pago.
    Filtros: fecha y/o estado de pago.
    """
    logger.info(
        f"[DASHBOARD] Reservas cancha {duenio.cancha_id} — "
        f"fecha={fecha} estado={estado}"
    )
    if not duenio.cancha_id:
        raise HTTPException(status_code=400, detail="Sin cancha asignada")

    query = (
        db.query(Reserva)
        .options(joinedload(Reserva.turno).joinedload(Turno.cancha))
        .join(Turno, Reserva.turno_id == Turno.id)
        .filter(Turno.cancha_id == duenio.cancha_id)
    )

    if fecha:
        query = query.filter(Turno.fecha == fecha)

    if estado:
        try:
            estado_enum = EstadoPago(estado)
            query = query.filter(Reserva.estado_pago == estado_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Estado inválido: '{estado}'. Usá: pendiente, aprobado o rechazado"
            )

    reservas = query.order_by(Turno.fecha, Turno.hora_inicio).all()
    logger.info(f"[DASHBOARD] {len(reservas)} reservas encontradas")

    resultado = []
    for r in reservas:
        resultado.append({
            "reserva_id":   r.id,
            # Datos del cliente
            "cliente":      r.nombre_cliente,
            "email":        r.email_cliente,
            "telefono":     r.telefono_cliente or "—",
            # Turno
            "fecha":        r.turno.fecha.strftime("%d/%m/%Y"),
            "hora_inicio":  str(r.turno.hora_inicio)[:5],
            "hora_fin":     str(r.turno.hora_fin)[:5],
            # Pago
            "estado_pago":  r.estado_pago.value,
            "tipo_pago":    "canje" if r.canje_fichas else "mercadopago",
            "mp_payment_id": r.mp_payment_id or "—",
            # Metadata
            "reservado_el": r.created_at.strftime("%d/%m/%Y %H:%M"),
            "usuario_id":   r.usuario_id,
        })

    return resultado


# ── GET /dashboard/turnos-hoy ─────────────────────────────────────────────────

@router.get("/turnos-hoy")
def turnos_hoy(
    fecha: Optional[date] = None,
    duenio: Usuario = Depends(require_duenio),
    db: Session = Depends(get_db),
):
    """
    Timeline completo del día (por defecto hoy):
    cada turno con su estado, datos del cliente si hay reserva, y tipo de pago.
    Parámetro opcional `fecha` para navegar entre días.
    """
    dia = fecha or date.today()
    logger.info(f"[DASHBOARD] Turnos del día {dia} — cancha {duenio.cancha_id}")

    if not duenio.cancha_id:
        raise HTTPException(status_code=400, detail="Sin cancha asignada")

    hoy = dia
    turnos = (
        db.query(Turno)
        .options(joinedload(Turno.reserva))
        .filter(Turno.cancha_id == duenio.cancha_id, Turno.fecha == hoy)
        .order_by(Turno.hora_inicio)
        .all()
    )

    resultado = []
    for t in turnos:
        if not t.reserva:
            resultado.append({
                "turno_id":    t.id,
                "hora_inicio": str(t.hora_inicio)[:5],
                "hora_fin":    str(t.hora_fin)[:5],
                "estado":      "libre",
                "cliente":     None,
                "email":       None,
                "telefono":    None,
                "estado_pago": None,
                "tipo_pago":   None,
                "reserva_id":  None,
                "mp_payment_id": None,
            })
        else:
            r = t.reserva
            resultado.append({
                "turno_id":    t.id,
                "hora_inicio": str(t.hora_inicio)[:5],
                "hora_fin":    str(t.hora_fin)[:5],
                "estado":      "pagado" if r.estado_pago == EstadoPago.APROBADO else "pendiente_pago",
                "cliente":     r.nombre_cliente,
                "email":       r.email_cliente,
                "telefono":    r.telefono_cliente or "—",
                "estado_pago": r.estado_pago.value,
                "tipo_pago":   "canje" if r.canje_fichas else "mercadopago",
                "reserva_id":  r.id,
                "mp_payment_id": r.mp_payment_id or "—",
            })

    libres    = sum(1 for t in resultado if t["estado"] == "libre")
    pagados   = sum(1 for t in resultado if t["estado"] == "pagado")
    pendientes= sum(1 for t in resultado if t["estado"] == "pendiente_pago")

    logger.info(
        f"[DASHBOARD] Hoy: {len(turnos)} turnos — "
        f"{libres} libres / {pagados} pagados / {pendientes} pendientes"
    )
    return {
        "fecha":     hoy.strftime("%d/%m/%Y"),
        "resumen":   {"libres": libres, "pagados": pagados, "pendientes": pendientes},
        "turnos":    resultado,
    }


# ── GET /dashboard/proximos-dias ─────────────────────────────────────────────

@router.get("/proximos-dias")
def proximos_dias(
    dias: int = 7,
    duenio: Usuario = Depends(require_duenio),
    db: Session = Depends(get_db),
):
    """
    Resumen de ocupación de los próximos N días (default: 7).
    Útil para ver de un vistazo qué días tienen más reservas.
    """
    logger.info(f"[DASHBOARD] Próximos {dias} días — cancha {duenio.cancha_id}")

    if not duenio.cancha_id:
        raise HTTPException(status_code=400, detail="Sin cancha asignada")
    if dias < 1 or dias > 30:
        raise HTTPException(status_code=400, detail="dias debe estar entre 1 y 30")

    hoy = date.today()
    resultado = []

    for delta in range(dias):
        fecha = hoy + timedelta(days=delta)

        turnos_dia = (
            db.query(Turno)
            .options(joinedload(Turno.reserva))
            .filter(Turno.cancha_id == duenio.cancha_id, Turno.fecha == fecha)
            .all()
        )

        total     = len(turnos_dia)
        libres    = sum(1 for t in turnos_dia if not t.reserva)
        pagados   = sum(1 for t in turnos_dia if t.reserva and t.reserva.estado_pago == EstadoPago.APROBADO)
        pendientes= sum(1 for t in turnos_dia if t.reserva and t.reserva.estado_pago == EstadoPago.PENDIENTE)

        resultado.append({
            "fecha":      fecha.strftime("%d/%m/%Y"),
            "dia_semana": fecha.strftime("%A"),   # Monday, Tuesday...
            "total":      total,
            "libres":     libres,
            "pagados":    pagados,
            "pendientes": pendientes,
            "ocupacion_pct": round((pagados / total * 100) if total else 0, 1),
        })

    logger.info(f"[DASHBOARD] Próximos {dias} días calculados")
    return resultado
