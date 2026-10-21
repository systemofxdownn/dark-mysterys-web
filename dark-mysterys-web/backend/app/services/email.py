"""
Envío de correo.

En desarrollo (email_backend=console) los mensajes se registran en el log y,
además, se exponen en el endpoint de administración de "bandeja de salida" para
poder probar la verificación de correo y la recuperación sin un SMTP real.

En producción (email_backend=smtp) se envían por SMTP.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from ..config import settings

logger = logging.getLogger("darkmysterys.email")

# Bandeja de salida en memoria (solo desarrollo/pruebas)
OUTBOX: list[dict] = []


def send_email(to: str, subject: str, body: str) -> None:
    record = {"to": to, "subject": subject, "body": body}
    if settings.email_backend == "console" or not settings.smtp_host:
        logger.info("[EMAIL:console] to=%s subject=%s\n%s", to, subject, body)
        OUTBOX.append(record)
        if len(OUTBOX) > 200:
            del OUTBOX[:-200]
        return

    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
    OUTBOX.append(record)


def invitation_email(identifier: str, token: str, link_base: str = "/") -> None:
    body = (
        f"Bienvenido/a a Dark Mystery's.\n\n"
        f"Tu identificador de cuenta es: {identifier}\n"
        f"Activa tu cuenta y define tu contraseña en el siguiente enlace:\n\n"
        f"{link_base}#/first-access?token={token}\n\n"
        f"Este enlace es de un solo uso y caduca en {settings.invitation_token_expire_hours} horas.\n"
        f"Al ingresar deberás registrar un correo electrónico obligatorio."
    )
    send_email("", "Dark Mystery's — Invitación de cuenta", body)


def reset_email(identifier: str, token: str, link_base: str = "/") -> None:
    body = (
        f"Recuperación de contraseña — Dark Mystery's\n\n"
        f"Cuenta: {identifier}\n"
        f"Restablece tu contraseña en:\n\n"
        f"{link_base}#/reset?token={token}\n\n"
        f"El enlace caduca en {settings.reset_token_expire_minutes} minutos."
    )
    send_email("", "Dark Mystery's — Recuperación de contraseña", body)


def verify_email(to: str, token: str, link_base: str = "/") -> None:
    body = (
        f"Verificación de correo — Dark Mystery's\n\n"
        f"Confirma tu correo en:\n\n{link_base}#/verify-email?token={token}\n\n"
        f"El enlace caduca en {settings.email_verify_token_expire_hours} horas."
    )
    send_email(to, "Dark Mystery's — Verificación de correo", body)
