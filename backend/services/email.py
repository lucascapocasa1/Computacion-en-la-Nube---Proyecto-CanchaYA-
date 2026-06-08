"""
services/email.py
-----------------
Servicio de envío de emails transaccionales usando Resend.
Si no hay API Key configurada, solo loggea el email (modo silencioso).

Resend free tier: 3.000 mails/mes, sin tarjeta de crédito.
Registro en https://resend.com
"""

import logging
import resend
from ..core.config import settings

logger = logging.getLogger(__name__)


def enviar_confirmacion(reserva, turno) -> bool:
    """
    Envía email de confirmación de reserva al cliente.

    Args:
        reserva: objeto ORM Reserva
        turno: objeto ORM Turno (con .cancha cargado)

    Returns:
        True si el email se envió, False si hubo error o no hay API Key.
    """
    if not settings.RESEND_API_KEY:
        logger.info(
            f"[EMAIL MOCK] Confirmación para {reserva.email_cliente}: "
            f"Reserva #{reserva.id} en {turno.cancha.nombre} "
            f"el {turno.fecha} a las {turno.hora_inicio}"
        )
        return False

    resend.api_key = settings.RESEND_API_KEY

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
      <h1 style="color: #16a34a;">¡Reserva confirmada! ⚽</h1>

      <p>Hola <strong>{reserva.nombre_cliente}</strong>,</p>
      <p>Tu reserva está registrada. Estos son los detalles:</p>

      <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
        <tr style="background: #f0fdf4;">
          <td style="padding: 10px; border: 1px solid #d1fae5;"><strong>Cancha</strong></td>
          <td style="padding: 10px; border: 1px solid #d1fae5;">{turno.cancha.nombre} ({turno.cancha.tipo.replace('_', ' ')})</td>
        </tr>
        <tr>
          <td style="padding: 10px; border: 1px solid #d1fae5;"><strong>Fecha</strong></td>
          <td style="padding: 10px; border: 1px solid #d1fae5;">{turno.fecha.strftime('%d/%m/%Y')}</td>
        </tr>
        <tr style="background: #f0fdf4;">
          <td style="padding: 10px; border: 1px solid #d1fae5;"><strong>Horario</strong></td>
          <td style="padding: 10px; border: 1px solid #d1fae5;">{turno.hora_inicio.strftime('%H:%M')} – {turno.hora_fin.strftime('%H:%M')}</td>
        </tr>
        <tr>
          <td style="padding: 10px; border: 1px solid #d1fae5;"><strong>Reserva #</strong></td>
          <td style="padding: 10px; border: 1px solid #d1fae5;">{reserva.id}</td>
        </tr>
        <tr style="background: #f0fdf4;">
          <td style="padding: 10px; border: 1px solid #d1fae5;"><strong>Estado de pago</strong></td>
          <td style="padding: 10px; border: 1px solid #d1fae5;">{reserva.estado_pago.value.upper()}</td>
        </tr>
      </table>

      <p style="color: #6b7280; font-size: 14px;">
        Si tenés alguna duda, respondé este email.
      </p>

      <p>¡Hasta la cancha! 🥅</p>
    </div>
    """

    try:
        params = resend.Emails.SendParams(
            from_=settings.FROM_EMAIL,
            to=[reserva.email_cliente],
            subject=f"✅ Reserva confirmada – {turno.cancha.nombre} – {turno.fecha}",
            html=html_body,
        )
        response = resend.Emails.send(params)
        logger.info(f"Email enviado a {reserva.email_cliente}: {response}")
        return True
    except Exception as e:
        logger.error(f"Error enviando email a {reserva.email_cliente}: {e}")
        return False
