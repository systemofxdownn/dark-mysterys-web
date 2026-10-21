"""Notificaciones internas del sitio (según decisión: DENTRO DEL SITIO)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Notification


def notify(db: Session, user_id: int | None, kind: str, title: str, body: str | None = None,
           link: str | None = None) -> Notification | None:
    if user_id is None:
        return None
    n = Notification(user_id=user_id, kind=kind, title=title, body=body, link=link)
    db.add(n)
    return n


def notify_many(db: Session, user_ids: list[int], kind: str, title: str,
                body: str | None = None, link: str | None = None) -> None:
    for uid in set(user_ids):
        notify(db, uid, kind, title, body, link)
