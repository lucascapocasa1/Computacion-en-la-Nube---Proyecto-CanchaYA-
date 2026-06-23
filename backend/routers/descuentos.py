import logging
from datetime import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..models.models import Cancha, Descuento, Usuario
from ..schemas.schemas import DescuentoCreate, DescuentoResponse, MessageResponse
from .auth import require_duenio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/descuentos", tags=["descuentos"])


def _hora_valida(h: str) -> time:
    try:
        partes = h.split(":")
        return time(int(partes[0]), int(partes[1]))
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail=f"Hora inválida: {h}. Usá HH:MM")


def _validar_duenio_cancha(duenio: Usuario, cancha_id: int):
    if duenio.cancha_id != cancha_id:
        raise HTTPException(
            status_code=403,
            detail="No podés gestionar descuentos de una cancha que no te pertenece."
        )


@router.get("", response_model=list[DescuentoResponse])
def listar_descuentos(
    cancha_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Lista descuentos, opcionalmente filtrados por cancha."""
    query = db.query(Descuento)
    if cancha_id:
        query = query.filter(Descuento.cancha_id == cancha_id)
    descuentos = query.all()
    return [
        DescuentoResponse(
            id=d.id,
            cancha_id=d.cancha_id,
            hora_desde=str(d.hora_desde)[:5],
            hora_hasta=str(d.hora_hasta)[:5],
            porcentaje=d.porcentaje,
            activo=d.activo,
        )
        for d in descuentos
    ]


@router.post("", response_model=DescuentoResponse, status_code=201)
def crear_descuento(
    payload: DescuentoCreate,
    duenio: Usuario = Depends(require_duenio),
    db: Session = Depends(get_db),
):
    """Crea un descuento para la cancha del dueño autenticado."""
    cancha_id = duenio.cancha_id
    if not cancha_id:
        raise HTTPException(status_code=400, detail="Tu cuenta no tiene cancha asignada")

    cancha = db.query(Cancha).filter(Cancha.id == cancha_id).first()
    if not cancha:
        raise HTTPException(status_code=404, detail="Cancha no encontrada")

    hora_desde = _hora_valida(payload.hora_desde)
    hora_hasta = _hora_valida(payload.hora_hasta)

    if hora_desde >= hora_hasta:
        raise HTTPException(status_code=400, detail="hora_desde debe ser menor a hora_hasta")

    descuento = Descuento(
        cancha_id=cancha_id,
        hora_desde=hora_desde,
        hora_hasta=hora_hasta,
        porcentaje=payload.porcentaje,
        activo=True,
    )
    db.add(descuento)
    db.commit()
    db.refresh(descuento)

    logger.info(
        f"[DESCUENTO] Creado: cancha={cancha_id} "
        f"{payload.hora_desde}-{payload.hora_hasta} {payload.porcentaje}%"
    )

    return DescuentoResponse(
        id=descuento.id,
        cancha_id=descuento.cancha_id,
        hora_desde=str(descuento.hora_desde)[:5],
        hora_hasta=str(descuento.hora_hasta)[:5],
        porcentaje=descuento.porcentaje,
        activo=descuento.activo,
    )


@router.put("/{descuento_id}/toggle", response_model=DescuentoResponse)
def toggle_descuento(
    descuento_id: int,
    duenio: Usuario = Depends(require_duenio),
    db: Session = Depends(get_db),
):
    """Activa/desactiva un descuento."""
    descuento = db.query(Descuento).filter(Descuento.id == descuento_id).first()
    if not descuento:
        raise HTTPException(status_code=404, detail="Descuento no encontrado")

    _validar_duenio_cancha(duenio, descuento.cancha_id)

    descuento.activo = not descuento.activo
    db.commit()
    db.refresh(descuento)

    logger.info(
        f"[DESCUENTO] Toggle {descuento_id}: {'activo' if descuento.activo else 'inactivo'}"
    )

    return DescuentoResponse(
        id=descuento.id,
        cancha_id=descuento.cancha_id,
        hora_desde=str(descuento.hora_desde)[:5],
        hora_hasta=str(descuento.hora_hasta)[:5],
        porcentaje=descuento.porcentaje,
        activo=descuento.activo,
    )


@router.delete("/{descuento_id}", response_model=MessageResponse)
def eliminar_descuento(
    descuento_id: int,
    duenio: Usuario = Depends(require_duenio),
    db: Session = Depends(get_db),
):
    """Elimina un descuento."""
    descuento = db.query(Descuento).filter(Descuento.id == descuento_id).first()
    if not descuento:
        raise HTTPException(status_code=404, detail="Descuento no encontrado")

    _validar_duenio_cancha(duenio, descuento.cancha_id)

    db.delete(descuento)
    db.commit()

    logger.info(f"[DESCUENTO] Eliminado {descuento_id}")
    return MessageResponse(message="Descuento eliminado correctamente")
