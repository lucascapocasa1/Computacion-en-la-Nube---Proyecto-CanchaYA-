"""
routers/reservas.py
-------------------
Lógica de reservas con la lógica correcta de disponibilidad:

  PENDIENTE → el turno NO se marca como no-disponible todavía.
              Existe una reserva en DB para bloquear dobles intentos (UNIQUE en turno_id),
              pero el turno sigue apareciendo en la UI hasta que el pago se confirme.

  APROBADO  → el turno.disponible = False (bloqueado definitivamente).
              Se suma 1 ficha al usuario si está logueado.

  RECHAZADO → la reserva se elimina y el turno queda libre.

¿Por qué no bloquear el turno al reservar?
  Si el usuario reserva y nunca paga, el turno queda bloqueado para siempre.
  Con este modelo, la reserva PENDIENTE actúa como "lock de sesión":
  nadie más puede reservar ese turno (UniqueConstraint), pero si el pago
  no llega, la reserva se puede limpiar (manual o con un job de expiración).
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError
from typing import Optional

from ..db.database import get_db
from ..models.models import Turno, Reserva, Ficha, EstadoPago, RolUsuario, Usuario
from ..schemas.schemas import ReservaCreate, ReservaResponse, MessageResponse, FichaResponse
from ..services.email import enviar_confirmacion
from ..routers.auth import get_usuario_actual, require_usuario

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reservas", tags=["reservas"])


# ── Helper: sumar ficha de fidelidad ──────────────────────────────────────

def _sumar_ficha(db: Session, usuario_id: int, cancha_id: int):
    """
    Suma 1 ficha al usuario para la cancha indicada.
    Si no existe el registro, lo crea. Usa upsert manual.
    """
    ficha = (
        db.query(Ficha)
        .filter(Ficha.usuario_id == usuario_id, Ficha.cancha_id == cancha_id)
        .first()
    )
    if ficha:
        ficha.fichas_acumuladas += 1
        logger.info(
            f"[FICHAS] Usuario {usuario_id} + 1 ficha en cancha {cancha_id} "
            f"→ total {ficha.fichas_acumuladas}"
        )
    else:
        ficha = Ficha(usuario_id=usuario_id, cancha_id=cancha_id, fichas_acumuladas=1)
        db.add(ficha)
        logger.info(f"[FICHAS] Primera ficha de usuario {usuario_id} en cancha {cancha_id}")


# ── POST /reservas ─────────────────────────────────────────────────────────

@router.post("", response_model=ReservaResponse, status_code=201)
def crear_reserva(
    payload: ReservaCreate,
    db: Session = Depends(get_db),
    usuario_actual: Optional[Usuario] = Depends(get_usuario_actual),
):
    """
    Crea una reserva en estado PENDIENTE.
    El turno NO se bloquea hasta que el pago sea aprobado.
    Si el usuario está logueado, se asocia la reserva a su cuenta.
    """
    logger.info(
        f"[RESERVA] Nueva reserva: turno={payload.turno_id} "
        f"cliente='{payload.nombre_cliente}' email={payload.email_cliente}"
    )

    try:
        # selectinload + with_for_update: evita el error de LEFT OUTER JOIN con FOR UPDATE
        turno = (
            db.query(Turno)
            .options(selectinload(Turno.cancha))
            .filter(Turno.id == payload.turno_id)
            .with_for_update()
            .first()
        )

        if not turno:
            logger.warning(f"[RESERVA] Turno {payload.turno_id} no encontrado")
            raise HTTPException(status_code=404, detail="Turno no encontrado")

        if not turno.disponible:
            logger.warning(f"[RESERVA] Turno {payload.turno_id} ya está ocupado (pago aprobado)")
            raise HTTPException(
                status_code=409,
                detail="Este turno ya fue reservado y pagado. Elegí otro horario."
            )

        # Verificar que no exista ya una reserva PENDIENTE para este turno
        reserva_existente = db.query(Reserva).filter(Reserva.turno_id == payload.turno_id).first()
        if reserva_existente:
            if reserva_existente.estado_pago == EstadoPago.PENDIENTE:
                logger.warning(
                    f"[RESERVA] Turno {payload.turno_id} tiene reserva pendiente "
                    f"#{reserva_existente.id} — rechazando nueva solicitud"
                )
                raise HTTPException(
                    status_code=409,
                    detail="Este turno tiene una reserva en proceso de pago. "
                           "Si el pago no se completa en unos minutos, el turno quedará libre."
                )

        # Determinar usuario asociado
        usuario_id = None
        if usuario_actual and usuario_actual.rol == RolUsuario.COMPRADOR:
            usuario_id = usuario_actual.id
            logger.info(f"[RESERVA] Asociando a usuario logueado id={usuario_id}")
        elif payload.usuario_id:
            usuario_id = payload.usuario_id
            logger.info(f"[RESERVA] Asociando a usuario_id={usuario_id} del payload")

        reserva = Reserva(
            turno_id=payload.turno_id,
            usuario_id=usuario_id,
            nombre_cliente=payload.nombre_cliente,
            email_cliente=payload.email_cliente,
            telefono_cliente=payload.telefono_cliente,
            estado_pago=EstadoPago.PENDIENTE,
            # El turno.disponible se mantiene en True hasta que el pago sea APROBADO
        )
        db.add(reserva)

        # NO modificamos turno.disponible aquí — solo cuando el pago se apruebe
        db.commit()
        db.refresh(reserva)

        logger.info(
            f"[RESERVA] Creada reserva #{reserva.id} para turno {payload.turno_id} "
            f"— estado: PENDIENTE (turno aún disponible visualmente)"
        )

        # Email de confirmación (no bloquea el flujo si falla)
        try:
            enviar_confirmacion(reserva=reserva, turno=turno)
        except Exception as mail_error:
            logger.warning(f"[EMAIL] No se pudo enviar email confirmación: {mail_error}")

        return reserva

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"[RESERVA] IntegrityError al crear reserva: {e}")
        raise HTTPException(
            status_code=409,
            detail="El turno ya fue reservado (conflicto de concurrencia). Intentá con otro."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"[RESERVA] Error inesperado: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


# ── GET /reservas/mis-reservas ─────────────────────────────────────────────

@router.get("/mis-reservas", response_model=list[ReservaResponse])
def mis_reservas(
    usuario: Usuario = Depends(require_usuario),
    db: Session = Depends(get_db),
):
    """Historial de reservas del usuario logueado."""
    logger.info(f"[RESERVA] Consultando historial de usuario {usuario.id}")
    reservas = (
        db.query(Reserva)
        .options(joinedload(Reserva.turno).joinedload(Turno.cancha))
        .filter(Reserva.usuario_id == usuario.id)
        .order_by(Reserva.created_at.desc())
        .all()
    )
    logger.info(f"[RESERVA] {len(reservas)} reservas encontradas para usuario {usuario.id}")
    return reservas


# ── GET /reservas/mis-fichas ───────────────────────────────────────────────

@router.get("/mis-fichas", response_model=list[FichaResponse])
def mis_fichas(
    usuario: Usuario = Depends(require_usuario),
    db: Session = Depends(get_db),
):
    """Fichas de fidelidad del usuario logueado, por cancha."""
    logger.info(f"[FICHAS] Consultando fichas de usuario {usuario.id}")
    fichas = (
        db.query(Ficha)
        .options(joinedload(Ficha.cancha))
        .filter(Ficha.usuario_id == usuario.id)
        .all()
    )
    resultado = [
        FichaResponse(
            cancha_id=f.cancha_id,
            cancha_nombre=f.cancha.nombre,
            fichas_acumuladas=f.fichas_acumuladas,
            fichas_canjeadas=f.fichas_canjeadas,
            fichas_disponibles=f.fichas_disponibles,
            puede_canjear=f.fichas_disponibles >= 10,
        )
        for f in fichas
    ]
    logger.info(f"[FICHAS] Usuario {usuario.id} tiene fichas en {len(resultado)} canchas")
    return resultado


# ── POST /reservas/canjear ─────────────────────────────────────────────────

@router.post("/canjear", response_model=ReservaResponse, status_code=201)
def canjear_fichas(
    turno_id: int,
    usuario: Usuario = Depends(require_usuario),
    db: Session = Depends(get_db),
):
    """
    Canjea 10 fichas por un turno gratis en la misma cancha.
    Reglas:
      - El usuario debe tener >= 10 fichas disponibles en ESA cancha.
      - El turno debe estar disponible.
      - El turno debe pertenecer a la misma cancha de las fichas.
    """
    logger.info(f"[CANJE] Usuario {usuario.id} intenta canjear turno {turno_id}")

    turno = (
        db.query(Turno)
        .options(selectinload(Turno.cancha))
        .filter(Turno.id == turno_id)
        .with_for_update()
        .first()
    )
    if not turno:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    if not turno.disponible:
        raise HTTPException(status_code=409, detail="El turno ya está ocupado")

    # Verificar fichas disponibles para esta cancha
    ficha = (
        db.query(Ficha)
        .filter(Ficha.usuario_id == usuario.id, Ficha.cancha_id == turno.cancha_id)
        .first()
    )

    if not ficha or ficha.fichas_disponibles < 10:
        disponibles = ficha.fichas_disponibles if ficha else 0
        logger.warning(
            f"[CANJE] Usuario {usuario.id} no tiene suficientes fichas "
            f"en cancha {turno.cancha_id}: tiene {disponibles}, necesita 10"
        )
        raise HTTPException(
            status_code=400,
            detail=f"No tenés suficientes fichas en esta cancha. "
                   f"Tenés {disponibles}/10 necesarias."
        )

    try:
        # Crear la reserva como APROBADO directamente (es un canje)
        reserva = Reserva(
            turno_id=turno_id,
            usuario_id=usuario.id,
            nombre_cliente=usuario.nombre,
            email_cliente=usuario.email,
            estado_pago=EstadoPago.APROBADO,
            canje_fichas=True,
        )
        db.add(reserva)

        # Bloquear el turno
        turno.disponible = False

        # Descontar 10 fichas
        ficha.fichas_canjeadas += 10

        db.commit()
        db.refresh(reserva)

        logger.info(
            f"[CANJE] ✅ Turno {turno_id} canjeado por usuario {usuario.id}. "
            f"Fichas restantes: {ficha.fichas_disponibles}"
        )
        return reserva

    except IntegrityError as e:
        db.rollback()
        logger.error(f"[CANJE] IntegrityError: {e}")
        raise HTTPException(status_code=409, detail="El turno ya fue reservado")
    except Exception as e:
        db.rollback()
        logger.error(f"[CANJE] Error inesperado: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


# ── GET /reservas/{id} ─────────────────────────────────────────────────────

@router.get("/{reserva_id}", response_model=ReservaResponse)
def detalle_reserva(reserva_id: int, db: Session = Depends(get_db)):
    """Detalle de una reserva por ID."""
    logger.info(f"[RESERVA] Consultando detalle de reserva {reserva_id}")
    reserva = (
        db.query(Reserva)
        .options(joinedload(Reserva.turno).joinedload(Turno.cancha))
        .filter(Reserva.id == reserva_id)
        .first()
    )
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return reserva


# ── POST /reservas/cancelar/{id} ──────────────────────────────────────────

@router.post("/cancelar/{reserva_id}", response_model=MessageResponse)
def cancelar_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Optional[Usuario] = Depends(get_usuario_actual),
):
    """
    Cancela una reserva PENDIENTE y la elimina.
    El turno queda disponible para nuevas reservas.
    No se puede cancelar si el pago ya fue aprobado.

    Autorización:
      - Dueño de la cancha puede cancelar cualquier reserva pendiente de su cancha
      - Comprador puede cancelar sus propias reservas pendientes
      - Usuarios anónimos también pueden cancelar (por URL directa)
    """
    logger.info(f"[RESERVA] Cancelando reserva {reserva_id}")
    reserva = (
        db.query(Reserva)
        .options(joinedload(Reserva.turno).joinedload(Turno.cancha))
        .filter(Reserva.id == reserva_id)
        .first()
    )
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")

    if reserva.estado_pago == EstadoPago.APROBADO:
        raise HTTPException(
            status_code=400,
            detail="No se puede cancelar una reserva con pago aprobado."
        )

    # Verificar autorización
    if usuario_actual:
        if usuario_actual.rol == RolUsuario.DUENIO:
            if reserva.turno.cancha_id != usuario_actual.cancha_id:
                raise HTTPException(
                    status_code=403,
                    detail="No podés cancelar reservas de canchas que no te pertenecen."
                )
        elif usuario_actual.rol == RolUsuario.COMPRADOR:
            if reserva.usuario_id != usuario_actual.id:
                raise HTTPException(
                    status_code=403,
                    detail="No podés cancelar una reserva que no te pertenece."
                )

    turno = db.query(Turno).filter(Turno.id == reserva.turno_id).first()
    if turno:
        turno.disponible = True
        logger.info(f"[RESERVA] Turno {turno.id} liberado")

    db.delete(reserva)
    db.commit()
    logger.info(f"[RESERVA] Reserva {reserva_id} cancelada y eliminada")
    return MessageResponse(message="Reserva cancelada correctamente")
