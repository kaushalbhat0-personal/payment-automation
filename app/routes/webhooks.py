import json
import logging
import os

from flask import Blueprint, current_app, request
from app.services.payment_mapper import parse_payment_captured
from app.services.razorpay_verify import verify_razorpay_signature
from app.services.sheets_client import append_row_if_payment_new

class Webhooks:
    def __init__(self):
        self.bp = Blueprint("webhooks", __name__)
        self.logger = logging.getLogger(__name__)
        self.bp.add_url_rule(
        "/webhooks/razorpay",
        view_func=self.razorpay_webhook,
        methods=["POST"]
        )

    def razorpay_webhook(self):
        """
Razorpay Webhook Endpoint (payment.captured)
---
tags:
  - Webhooks

consumes:
  - application/json

parameters:
  - name: X-Razorpay-Signature
    in: header
    type: string
    required: false
    description: Razorpay webhook signature

  - name: body
    in: body
    required: true
    schema:
      type: object
      properties:
        event:
          type: string
          example: payment.captured
        payload:
          type: object
          properties:
            payment:
              type: object
              properties:
                entity:
                  type: object
                  properties:
                    id:
                      type: string
                      example: pay_test123
                    email:
                      type: string
                      example: test@gmail.com
                    contact:
                      type: string
                      example: "9999999999"
                    amount:
                      type: integer
                      example: 516300
                    status:
                      type: string
                      example: captured

responses:
  200:
    description: Success
  400:
    description: Invalid JSON
  401:
    description: Invalid signature
  500:
    description: Internal error
"""
       
        config = current_app.config["APP_CONFIG"]
        raw_body = request.get_data(cache=False)
        env_skip_webhook_verify = str(os.environ.get("SKIP_WEBHOOK_VERIFY", "")).strip().lower()
        skip_webhook_verify = bool(config.skip_webhook_verify) or (
            env_skip_webhook_verify == "true"
        )
        self.logger.info("skip_webhook_verify=%s", skip_webhook_verify)
        self.logger.info(
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
                self.logger.warning("Invalid Razorpay signature")
                return {"status": "error", "message": "invalid signature"}, 401

        try:
            payload = json.loads(raw_body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload root must be an object")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self.logger.warning("Invalid JSON payload")
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
                self.logger.info(
                    "Duplicate payment skipped (retry-safe): %s",
                    parsed_payment.payment_id,
                )
                return {"status": "duplicate_skipped"}, 200
        except ValueError as exc:
            self.logger.warning("Invalid payment.captured payload: %s", exc)
            return {"status": "error", "message": "invalid payload"}, 400
        except Exception:
            self.logger.exception("Failed processing payment.captured webhook")
            return {"status": "error", "message": "internal server error"}, 500

        return {"status": "ok"}, 200
