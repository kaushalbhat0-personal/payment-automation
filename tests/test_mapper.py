from app.services.payment_mapper import (
    parse_payment_captured,
    paise_to_inr,
    unix_to_ist_str,
)


def test_paise_to_inr():
    assert paise_to_inr(10050) == 100.5
    assert paise_to_inr(0) == 0.0
    assert paise_to_inr(None) == 0.0


def test_unix_to_ist_str_seconds():
    s = unix_to_ist_str(1704067200)
    assert "IST" in s or "2024" in s


def test_unix_to_ist_str_millis():
    s = unix_to_ist_str(1704067200000)
    assert "IST" in s


def test_parse_payment_captured_minimal():
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_123",
                    "amount": 49_900,
                    "status": "captured",
                    "email": "user@example.com",
                    "contact": "+919999999999",
                    "notes": {
                        "name": "Ada",
                        "preferred_batch": "A",
                        "mode": "online",
                    },
                    "created_at": 1704067200,
                }
            }
        },
    }
    row = parse_payment_captured(payload)
    assert row.payment_id == "pay_123"
    assert row.email == "user@example.com"
    assert row.contact == "+919999999999"
    assert row.amount_inr == 499.0
    assert row.status == "captured"
    assert row.name == "Ada"
    assert row.preferred_batch == "A"
    assert row.mode == "online"
    assert row.captured_at_ist.endswith("IST")
    vals = row.as_sheet_row()
    assert vals == [
        row.payment_id,
        row.name,
        row.email,
        row.contact,
        row.amount_inr,
        row.status,
        row.preferred_batch,
        row.mode,
        row.captured_at_ist,
    ]


def test_parse_payment_captured_missing_notes_defaults():
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_x",
                    "amount": 100,
                    "status": "captured",
                    "created_at": 1704067200,
                }
            }
        },
    }
    row = parse_payment_captured(payload)
    assert row.name == ""
    assert row.preferred_batch == ""
    assert row.mode == ""


def test_parse_payment_captured_bad_shape():
    try:
        parse_payment_captured({"payload": {}})
    except ValueError:
        return
    raise AssertionError("Expected ValueError")
