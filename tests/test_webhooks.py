import hashlib
import hmac
import json
from unittest.mock import patch

import pytest

from app import create_app


@pytest.fixture()
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "test_whsec")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "test_sheet")
    monkeypatch.setenv("GOOGLE_WORKSHEET_NAME", "Payments")
    fake_creds = tmp_path / "sa.json"
    fake_creds.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "x",
                "private_key_id": "x",
                "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----\n",
                "client_email": "x@x.iam.gserviceaccount.com",
                "client_id": "1",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(fake_creds))
    monkeypatch.setenv("SKIP_WEBHOOK_VERIFY", "")
    return create_app()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json["status"] == "ok"


def test_webhook_invalid_signature(client):
    res = client.post(
        "/webhooks/razorpay",
        data=b"{}",
        headers={"X-Razorpay-Signature": "wrong"},
        content_type="application/json",
    )
    assert res.status_code == 401


def test_webhook_valid_signature_ignores_other_events(client):
    body = b'{"event":"order.paid","payload":{}}'
    sig = hmac.new(b"test_whsec", body, hashlib.sha256).hexdigest()
    res = client.post(
        "/webhooks/razorpay",
        data=body,
        headers={"X-Razorpay-Signature": sig},
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.json["status"] == "ignored"


def test_webhook_invalid_json_with_skip(monkeypatch):
    monkeypatch.setenv("SKIP_WEBHOOK_VERIFY", "true")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "")
    app = create_app()
    c = app.test_client()
    res = c.post("/webhooks/razorpay", data="not-json", content_type="application/json")
    assert res.status_code == 400


def test_webhook_skip_verify_omits_signature(monkeypatch):
    """With SKIP_WEBHOOK_VERIFY, HMAC must not run (no header still OK for non-captured events)."""
    monkeypatch.setenv("SKIP_WEBHOOK_VERIFY", "true")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "must-not-be-used")
    app = create_app()
    c = app.test_client()
    body = b'{"event":"order.paid","payload":{}}'
    res = c.post("/webhooks/razorpay", data=body, content_type="application/json")
    assert res.status_code == 200
    assert res.json["status"] == "ignored"


@patch("app.routes.webhooks.append_row")
def test_payment_captured_appends(mock_append, client):
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test",
                    "amount": 10000,
                    "status": "captured",
                    "email": "e@e.com",
                    "contact": "91",
                    "notes": {"name": "n", "preferred_batch": "b", "mode": "m"},
                    "created_at": 1704067200,
                }
            }
        },
    }
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(b"test_whsec", raw, hashlib.sha256).hexdigest()
    res = client.post(
        "/webhooks/razorpay",
        data=raw,
        headers={"X-Razorpay-Signature": sig},
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.json["status"] == "ok"
    mock_append.assert_called_once()
