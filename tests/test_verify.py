import hashlib
import hmac

from app.services.razorpay_verify import verify_razorpay_signature


def test_accepts_valid_signature():
    secret = "whsec_test_secret"
    body = b'{"event":"payment.captured","payload":{}}'
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert verify_razorpay_signature(body, sig, secret) is True


def test_rejects_invalid_signature():
    body = b"{}"
    assert verify_razorpay_signature(body, "deadbeef", "mysecret") is False


def test_rejects_missing_secret():
    assert verify_razorpay_signature(b"{}", "abc", "") is False


def test_rejects_missing_header():
    assert verify_razorpay_signature(b"{}", None, "secret") is False
