import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..models.models import Cancha, Usuario, RolUsuario
from ..schemas.schemas import CanchaResponse, PrecioUpdate, MessageResponse
from .auth import require_duenio

logger = logging.getLogger(__name__)
router = APIRouter(tags=["canchas"])


@router.put("/canchas/{cancha_id}/precio", response_model=CanchaResponse)
def actualizar_precio(
    cancha_id: int,
    payload: PrecioUpdate,
    duenio: Usuario = Depends(require_duenio),
    db: Session = Depends(get_db),
):
    """Actualiza el precio por hora de una cancha (solo dueño de esa cancha)."""
    logger.info(f"[PRECIO] Dueño {duenio.id} actualiza precio cancha {cancha_id} → {payload.precio_hora}")

    if duenio.cancha_id != cancha_id:
        raise HTTPException(
            status_code=403,
            detail="No podés modificar el precio de una cancha que no te pertenece."
        )

    cancha = db.query(Cancha).filter(Cancha.id == cancha_id).first()
    if not cancha:
        raise HTTPException(status_code=404, detail="Cancha no encontrada")

    cancha.precio_hora = payload.precio_hora
    db.commit()
    db.refresh(cancha)

    logger.info(f"[PRECIO] Cancha {cancha_id} nuevo precio: ${payload.precio_hora}")
    return cancha
