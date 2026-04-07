from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.models import ParsedPaymentRow

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)


def paise_to_inr(amount_paise: int | float | None) -> float:
    if amount_paise is None:
        return 0.0
    return round(float(amount_paise) / 100.0, 2)


def unix_to_ist_str(created_at: int | float | None) -> str:
    if created_at is None:
        return ""
    ts = float(created_at)
    if ts > 1e12:
        ts = ts / 1000.0
    dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt_utc.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S IST")


def _str_or_empty(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalized_note_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _notes_dict(entity: dict[str, Any]) -> dict[str, Any]:
    notes = entity.get("notes")
    if isinstance(notes, dict):
        return notes
    if notes is None:
        return {}
    return {}


def parse_payment_captured(payload: dict[str, Any]) -> ParsedPaymentRow:
    pay_wrap = payload.get("payload") or {}
    payment = pay_wrap.get("payment") or {}
    entity = payment.get("entity")
    if not isinstance(entity, dict):
        raise ValueError("Missing payload.payment.entity")

    notes = _notes_dict(entity)
    logger.info("Razorpay notes payload: %s", notes)
    mode = (
        notes.get("mode")
        or notes.get("select_mode")
        or notes.get("Mode")
        or ""
    )

    amount = entity.get("amount")
    if amount is None:
        raise ValueError("Missing payment amount")

    return ParsedPaymentRow(
        payment_id=_str_or_empty(entity.get("id")),
        email=_str_or_empty(entity.get("email")),
        contact=_str_or_empty(entity.get("contact")),
        amount_inr=paise_to_inr(amount),
        status=_str_or_empty(entity.get("status")),
        name=_str_or_empty(notes.get("name")),
        preferred_batch=_str_or_empty(notes.get("preferred_batch")),
        mode=_normalized_note_value(mode),
        captured_at_ist=unix_to_ist_str(entity.get("created_at")),
    )
