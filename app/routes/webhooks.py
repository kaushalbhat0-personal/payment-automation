import json
import logging
import os

from flask import Blueprint, current_app, request
from app.services.payment_mapper import parse_payment_captured
from app.services.razorpay_verify import verify_razorpay_signature
from app.services.sheets_client import append_row_if_payment_new

bp = Blueprint("webhooks", __name__)
logger = logging.getLogger(__name__)


@bp.post("/webhooks/razorpay")
def razorpay_webhook():
    config = current_app.config["APP_CONFIG"]
    raw_body = request.get_data(cache=False)
    env_skip_webhook_verify = str(os.environ.get("SKIP_WEBHOOK_VERIFY", "")).strip().lower()
    skip_webhook_verify = bool(config.skip_webhook_verify) or (
        env_skip_webhook_verify == "true"
    )
    logger.info("skip_webhook_verify=%s", skip_webhook_verify)
    logger.info(
        "Signature verification %s",
        "skipped" if skip_webhook_verify else "enabled",
    )

    if not skip_webhook_verify:
        signature = request.headers.get("X-Razorpay-Signature")
        is_valid = verify_razorpay_signature(
            raw_body=raw_body,
            signature_header=signature,
            secret=config.razorpay_webhook_secret,
        )
        if not is_valid:
            logger.warning("Invalid Razorpay signature")
            return {"status": "error", "message": "invalid signature"}, 401

    try:
        payload = json.loads(raw_body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("payload root must be an object")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        logger.warning("Invalid JSON payload")
        return {"status": "error", "message": "invalid json"}, 400

    event = payload.get("event")
    if event != "payment.captured":
        return {"status": "ignored"}, 200

    try:
        parsed_payment = parse_payment_captured(payload)
        inserted = append_row_if_payment_new(
            config,
            parsed_payment.payment_id,
            parsed_payment.as_sheet_row(),
        )
        if not inserted:
            logger.info(
                "Duplicate payment skipped (retry-safe): %s",
                parsed_payment.payment_id,
            )
            return {"status": "duplicate_skipped"}, 200
    except ValueError as exc:
        logger.warning("Invalid payment.captured payload: %s", exc)
        return {"status": "error", "message": "invalid payload"}, 400
    except Exception:
        logger.exception("Failed processing payment.captured webhook")
        return {"status": "error", "message": "internal server error"}, 500

    return {"status": "ok"}, 200
