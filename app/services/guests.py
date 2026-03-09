from __future__ import annotations

from uuid import uuid4

from fastapi import Request


def get_guest_id(request: Request) -> str | None:
    guest_id = request.session.get("guest_id")
    if guest_id and isinstance(guest_id, str):
        return guest_id
    return None


def get_or_create_guest_id(request: Request) -> str:
    guest_id = get_guest_id(request)
    if guest_id:
        return guest_id
    guest_id = uuid4().hex
    request.session["guest_id"] = guest_id
    return guest_id

