"""Notificaciones push — abstracción sobre Firebase Cloud Messaging (PARTE 2-E).

En producción se inyecta un backend FCM real (credenciales de servicio). Aquí el
backend por defecto registra en consola, de modo que el resto del sistema es
totalmente funcional y testeable sin credenciales.
"""
from __future__ import annotations

import logging
import os
from typing import Protocol

logger = logging.getLogger("cilantro.push")


class PushBackend(Protocol):
    def send(self, token: str, title: str, body: str) -> bool: ...


class ConsolePush:
    """Backend de desarrollo: registra la notificación."""

    def send(self, token: str, title: str, body: str) -> bool:
        logger.info("PUSH -> %s | %s: %s", token, title, body)
        return True


class FCMPush:
    """Backend Firebase Cloud Messaging (requiere `firebase-admin`)."""

    def __init__(self):
        import firebase_admin
        from firebase_admin import credentials
        cred_path = os.environ["FCM_CREDENTIALS"]
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(cred_path))
        from firebase_admin import messaging
        self._messaging = messaging

    def send(self, token: str, title: str, body: str) -> bool:
        msg = self._messaging.Message(
            notification=self._messaging.Notification(title=title, body=body),
            token=token)
        self._messaging.send(msg)
        return True


def get_backend() -> PushBackend:
    """Elige FCM si hay credenciales; si no, consola."""
    if os.environ.get("FCM_CREDENTIALS"):
        try:
            return FCMPush()
        except Exception:
            logger.warning("FCM no disponible, usando ConsolePush.")
    return ConsolePush()


def notify(token: str, title: str, body: str) -> bool:
    return get_backend().send(token, title, body)
