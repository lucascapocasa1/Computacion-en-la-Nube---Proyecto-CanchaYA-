"""
routers/pagos.py — Mercado Pago + confirmación manual por payment_id

PROBLEMA RAÍZ del webhook local:
  MP no puede llamar a localhost:8000/pagos/webhook porque localhost
  no es una URL pública. Por eso el pago queda en PENDIENTE para siempre.

SOLUCIÓN para desarrollo local:
  1. El frontend pide GET /pagos/verificar/{reserva_id} después de que el
     usuario paga en MP. Este endpoint le pregunta directamente a la API de
     MP el estado del pago usando el preference_id guardado.
  2. Si el pago fue aprobado → lo confirma en la DB sin necesitar webhook.
  3. El dueño también puede hacer GET /pagos/verificar/{reserva_id} desde
     el dashboard para forzar la verificación.

Para producción (DO con URL pública): el webhook funciona normalmente.
"""

import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from ..db.database import get_db
from ..models.models import Reserva, Turno, EstadoPago
from ..schemas.schemas import PagoConfirmacion, ReservaResponse
from ..core.config import settings
from .reservas import _sumar_ficha

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pagos", tags=["pagos"])
MP_API = "https://api.mercadopago.com"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _es_url_local(url: str) -> bool:
    return "localhost" in url or "127.0.0.1" in url


def _headers_mp() -> dict:
    return {
        "Authorization": f"Bearer {settings.MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _construir_body_preferencia(
    reserva_id: int, turno, nombre_cliente: str, email_cliente: str
) -> dict:
    """Arma el body de la preferencia de MP adaptado al entorno."""
    body: dict = {
        "items": [{
            "id": str(turno.id),
            "title": f"{turno.cancha.nombre} · {turno.fecha} {str(turno.hora_inicio)[:5]}",
            "description": f"Cancha {turno.cancha.tipo.replace('_', ' ')} – 1 hora",
            "quantity": 1,
            "currency_id": "ARS",
            "unit_price": float(turno.cancha.precio_hora),
        }],
        "payer": {"name": nombre_cliente, "email": email_cliente},
        "external_reference": str(reserva_id),
        "statement_descriptor": "CANCHAYAS",
    }

    # back_urls y auto_return solo con URLs públicas (MP rechaza localhost)
    if not _es_url_local(settings.FRONTEND_URL):
        body["back_urls"] = {
            "success": f"{settings.FRONTEND_URL}/pago-exitoso.html?reserva_id={reserva_id}",
            "failure": f"{settings.FRONTEND_URL}/pago-fallido.html?reserva_id={reserva_id}",
            "pending": f"{settings.FRONTEND_URL}/index.html?reserva_id={reserva_id}",
        }
        body["auto_return"] = "approved"

    # notification_url (webhook) solo con URL pública
    if not _es_url_local(settings.BACKEND_URL):
        body["notification_url"] = f"{settings.BACKEND_URL}/pagos/webhook"
        logger.info(f"[MP] notification_url configurada: {settings.BACKEND_URL}/pagos/webhook")
    else:
        logger.warning(
            "[MP] BACKEND_URL es local → MP no puede enviar webhook. "
            "Usar GET /pagos/verificar/{reserva_id} para confirmar pagos manualmente."
        )

    return body


def _aprobar_reserva(db: Session, reserva: Reserva, payment_id: str = None):
    """Aprueba una reserva: bloquea turno y suma ficha."""
    logger.info(f"[PAGO] ✅ Aprobando reserva #{reserva.id} payment_id={payment_id}")

    reserva.estado_pago = EstadoPago.APROBADO
    if payment_id:
        reserva.mp_payment_id = str(payment_id)

    turno = db.query(Turno).filter(Turno.id == reserva.turno_id).first()
    if turno:
        turno.disponible = False
        logger.info(f"[PAGO] Turno {turno.id} → disponible=False")
    else:
        logger.error(f"[PAGO] ⚠️ Turno {reserva.turno_id} no encontrado al aprobar!")
        return

    if reserva.usuario_id and not reserva.canje_fichas and turno:
        _sumar_ficha(db, reserva.usuario_id, turno.cancha_id)


def _rechazar_reserva(db: Session, reserva: Reserva, payment_id: str = None):
    """Rechaza una reserva: libera el turno."""
    logger.info(f"[PAGO] ❌ Rechazando reserva #{reserva.id} payment_id={payment_id}")

    reserva.estado_pago = EstadoPago.RECHAZADO
    if payment_id:
        reserva.mp_payment_id = str(payment_id)

    turno = db.query(Turno).filter(Turno.id == reserva.turno_id).first()
    if turno and not turno.disponible:
        turno.disponible = True
        logger.info(f"[PAGO] Turno {turno.id} → disponible=True (liberado)")

'''
def _buscar_pago_por_preferencia(preference_id: str) -> dict | None:
    """
    #Busca en MP el pago asociado a una preference_id.
    #Retorna el objeto pago o None si no hay pago aún.
    #Usa la búsqueda de pagos por external_reference como alternativa.
    """
    if not preference_id or preference_id.startswith("mock"):
        return None

    token = settings.MP_ACCESS_TOKEN or ""
    if not token or "fake" in token:
        return None

    headers = {"Authorization": f"Bearer {token}"}

    # Buscar pagos por preference_id
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{MP_API}/v1/payments/search",
                params={"preference_id": preference_id, "limit": 1},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        resultados = data.get("results", [])
        if resultados:
            pago = resultados[0]
            logger.info(
                f"[MP-SEARCH] Pago encontrado por preference_id={preference_id}: "
                f"payment_id={pago.get('id')} status={pago.get('status')}"
            )
            return pago
        else:
            logger.info(f"[MP-SEARCH] Sin pagos para preference_id={preference_id} aún")
            return None

    except Exception as e:
        logger.error(f"[MP-SEARCH] Error buscando pago: {e}")
        return None
'''

def _buscar_pago_por_reserva(reserva_id: int) -> dict | None:
    """
    Busca el pago en MP usando external_reference (FORMA CORRECTA).
    """
    token = settings.MP_ACCESS_TOKEN or ""
    if not token or "fake" in token:
        return None

    headers = {"Authorization": f"Bearer {token}"}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{MP_API}/v1/payments/search",
                params={
                    "external_reference": str(reserva_id),
                    "sort": "date_created",
                    "criteria": "desc",
                    "limit": 1,
                },
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        resultados = data.get("results", [])
        if resultados:
            pago = resultados[0]
            logger.info(
                f"[MP-SEARCH] Pago encontrado: payment_id={pago.get('id')} status={pago.get('status')}"
            )
            return pago

        logger.info(f"[MP-SEARCH] Sin pagos para reserva {reserva_id}")
        return None

    except Exception as e:
        logger.error(f"[MP-SEARCH] Error: {e}")
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/link/{reserva_id}")
def obtener_link_pago(reserva_id: int, db: Session = Depends(get_db)):
    """
    Crea (o reutiliza) la preferencia MP y devuelve el checkout URL.
    Modo simulacion si no hay token configurado.
    """
    logger.info(f"[MP] Solicitando link de pago para reserva {reserva_id}")

    reserva = (
        db.query(Reserva)
        .options(joinedload(Reserva.turno).joinedload(Turno.cancha))
        .filter(Reserva.id == reserva_id)
        .first()
    )
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")

    if reserva.estado_pago == EstadoPago.APROBADO:
        raise HTTPException(status_code=400, detail="Esta reserva ya está pagada")

    token = settings.MP_ACCESS_TOKEN or ""
    if not token or "fake" in token:
        logger.info("[MP] Sin token real → modo simulacion")
        return {"checkout_url": None, "preference_id": "mock", "modo": "simulacion",
                "mensaje": "Token MP no configurado. Usá 'Simular pago'."}

    turno = reserva.turno

    # Reutilizar preferencia si existe
    if reserva.mp_preference_id and not reserva.mp_preference_id.startswith("mock"):
        logger.info(f"[MP] Reutilizando preferencia existente: {reserva.mp_preference_id}")
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    f"{MP_API}/checkout/preferences/{reserva.mp_preference_id}",
                    headers=_headers_mp(),
                )
                resp.raise_for_status()
                data = resp.json()
            url = data.get("sandbox_init_point") or data.get("init_point")
            return {
                "checkout_url": url,
                "preference_id": reserva.mp_preference_id,
                "modo": "sandbox",
                "nota": "Después de pagar, volvé y hacé click en 'Verificar pago' para confirmar.",
            }
        except Exception as e:
            logger.warning(f"[MP] Error reutilizando preferencia: {e} — creando nueva")

    # Crear nueva preferencia
    body = _construir_body_preferencia(
        reserva_id, turno, reserva.nombre_cliente, reserva.email_cliente
    )
    logger.debug(f"[MP] Body preferencia: {body}")

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                f"{MP_API}/checkout/preferences",
                json=body,
                headers=_headers_mp(),
            )

        if resp.status_code != 201:
            err = resp.json()
            logger.error(f"[MP] Error {resp.status_code}: {err}")
            raise HTTPException(
                status_code=502,
                detail=f"Mercado Pago rechazó la solicitud: {err.get('message', resp.text)}"
            )

        pref = resp.json()
        reserva.mp_preference_id = pref["id"]
        db.commit()

        url = pref.get("sandbox_init_point") or pref.get("init_point")
        logger.info(f"[MP] Preferencia creada: {pref['id']}")

        return {
            "checkout_url": url,
            "preference_id": pref["id"],
            "modo": "sandbox",
            "nota": "Después de pagar, volvé y hacé click en 'Verificar pago' para confirmar.",
        }

    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.error("[MP] Timeout con Mercado Pago")
        raise HTTPException(status_code=504, detail="Timeout al conectar con Mercado Pago")
    except Exception as e:
        logger.error(f"[MP] Error inesperado: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Error con Mercado Pago: {str(e)}")


@router.get("/verificar/{reserva_id}")
def verificar_pago(reserva_id: int, db: Session = Depends(get_db)):
    """
    ENDPOINT CLAVE PARA DESARROLLO LOCAL.

    Como MP no puede llamar a localhost por webhook, este endpoint
    le pregunta activamente a la API de MP si el pago fue realizado.

    El frontend lo llama después de que el usuario vuelve del checkout de MP.
    El dueño también puede usarlo desde el dashboard para actualizar el estado.

    Retorna el estado actualizado de la reserva.
    """
    logger.info(f"[VERIFICAR] Verificando pago de reserva {reserva_id}")

    reserva = (
        db.query(Reserva)
        .options(joinedload(Reserva.turno).joinedload(Turno.cancha))
        .filter(Reserva.id == reserva_id)
        .first()
    )
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")

    if reserva.estado_pago == EstadoPago.APROBADO:
        logger.info(f"[VERIFICAR] Reserva {reserva_id} ya estaba APROBADA")
        return {
            "reserva_id": reserva_id,
            "estado_pago": "aprobado",
            "mensaje": "El pago ya estaba confirmado.",
            "cambio": False,
        }

    token = settings.MP_ACCESS_TOKEN or ""
    if not token or "fake" in token:
        return {
            "reserva_id": reserva_id,
            "estado_pago": reserva.estado_pago.value,
            "mensaje": "Sin token MP configurado. Usá 'Simular pago'.",
            "cambio": False,
        }

    if not reserva.mp_preference_id or reserva.mp_preference_id.startswith("mock"):
        return {
            "reserva_id": reserva_id,
            "estado_pago": reserva.estado_pago.value,
            "mensaje": "Esta reserva no tiene una preferencia de MP asociada.",
            "cambio": False,
        }

    # Buscar el pago en MP por preference_id
    pago = _buscar_pago_por_reserva(reserva.id)

    if not pago:
        logger.info(f"[VERIFICAR] Sin pago registrado en MP para reserva {reserva_id}")
        return {
            "reserva_id": reserva_id,
            "estado_pago": "pendiente",
            "mensaje": "MP no registra ningún pago para esta reserva todavía.",
            "cambio": False,
        }

    mp_status = pago.get("status")
    payment_id = str(pago.get("id"))
    logger.info(f"[VERIFICAR] MP status={mp_status} payment_id={payment_id}")

    if mp_status == "approved":
        _aprobar_reserva(db, reserva, payment_id)
        db.commit()
        logger.info(f"[VERIFICAR] ✅ Reserva {reserva_id} → APROBADA via verificación activa")
        return {
            "reserva_id": reserva_id,
            "estado_pago": "aprobado",
            "payment_id": payment_id,
            "mensaje": "¡Pago confirmado! El turno está reservado.",
            "cambio": True,
        }
    elif mp_status in ("rejected", "cancelled"):
        _rechazar_reserva(db, reserva, payment_id)
        db.commit()
        logger.info(f"[VERIFICAR] Reserva {reserva_id} → RECHAZADA")
        return {
            "reserva_id": reserva_id,
            "estado_pago": "rechazado",
            "payment_id": payment_id,
            "mensaje": "El pago fue rechazado. El turno quedó libre.",
            "cambio": True,
        }
    else:
        return {
            "reserva_id": reserva_id,
            "estado_pago": mp_status,
            "mensaje": f"Estado en MP: {mp_status}. Esperá unos segundos y volvé a verificar.",
            "cambio": False,
        }


@router.post("/webhook", include_in_schema=False)
async def webhook_mp(request: Request, db: Session = Depends(get_db)):
    """
    IPN de Mercado Pago. Funciona en producción (URL pública).
    En local no llega, usar GET /pagos/verificar/{id} en su lugar.
    Siempre responde 200 para que MP no reintente infinitamente.
    """
    params = dict(request.query_params)
    topic = params.get("topic") or params.get("type")
    payment_id = params.get("id")

    if not payment_id:
        try:
            body = await request.json()
            topic = body.get("type", topic)
            payment_id = body.get("data", {}).get("id")
        except Exception:
            pass

    logger.info(f"[WEBHOOK] IPN recibido: topic={topic} payment_id={payment_id}")

    if topic not in ("payment",):
        return {"status": "ignored", "topic": topic}
    if not payment_id:
        return {"status": "no_payment_id"}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{MP_API}/v1/payments/{payment_id}",
                headers={"Authorization": f"Bearer {settings.MP_ACCESS_TOKEN}"},
            )
            resp.raise_for_status()
            pago = resp.json()
    except Exception as e:
        logger.error(f"[WEBHOOK] Error consultando pago {payment_id}: {e}")
        return {"status": "mp_error"}

    status = pago.get("status")
    external_ref = pago.get("external_reference")
    logger.info(f"[WEBHOOK] payment_id={payment_id} status={status} reserva={external_ref}")

    if not external_ref:
        return {"status": "no_external_reference"}

    try:
        reserva_id = int(external_ref)
    except (ValueError, TypeError):
        return {"status": "invalid_external_reference"}

    reserva = db.query(Reserva).filter(Reserva.id == reserva_id).first()
    if not reserva:
        logger.warning(f"[WEBHOOK] Reserva {reserva_id} no encontrada")
        return {"status": "reserva_not_found"}

    if reserva.estado_pago == EstadoPago.APROBADO:
        logger.info(f"[WEBHOOK] Reserva {reserva_id} ya estaba aprobada, ignorando")
        return {"status": "already_approved"}

    if status == "approved":
        _aprobar_reserva(db, reserva, str(payment_id))
        db.commit()
        return {"status": "ok", "reserva_id": reserva_id, "mp_status": status}
    elif status in ("rejected", "cancelled"):
        _rechazar_reserva(db, reserva, str(payment_id))
        db.commit()
        return {"status": "ok", "reserva_id": reserva_id, "mp_status": status}
    else:
        logger.info(f"[WEBHOOK] Estado {status} no final, ignorando")
        return {"status": "pending_no_change", "mp_status": status}


@router.post("/mock-confirmar", response_model=ReservaResponse)
def mock_confirmar_pago(payload: PagoConfirmacion, db: Session = Depends(get_db)):
    """Confirma o rechaza un pago de forma local, sin pasar por MP. Para demos."""
    logger.info(f"[MOCK] reserva={payload.reserva_id} status={payload.status}")

    reserva = (
        db.query(Reserva)
        .options(joinedload(Reserva.turno).joinedload(Turno.cancha))
        .filter(Reserva.id == payload.reserva_id)
        .first()
    )
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")

    if reserva.estado_pago == EstadoPago.APROBADO:
        raise HTTPException(status_code=400, detail="Esta reserva ya fue pagada")

    if payload.status == "approved":
        _aprobar_reserva(db, reserva, "mock-payment-approved")
    else:
        _rechazar_reserva(db, reserva, "mock-payment-rejected")

    db.commit()
    db.refresh(reserva)
    logger.info(f"[MOCK] Reserva {payload.reserva_id} → {reserva.estado_pago}")
    return reserva
