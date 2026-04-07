import hashlib
import hmac


def verify_razorpay_signature(
    raw_body: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    if not secret or not signature_header:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
