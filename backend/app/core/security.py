import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.config import settings


def hash_pin(pin: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 120_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_pin(pin: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        algorithm, salt, digest = stored_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    next_digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 120_000).hex()
    return hmac.compare_digest(next_digest, digest)


def create_owner_token(owner_id: str, ttl_seconds: int = 60 * 60 * 24 * 30) -> str:
    payload = {"owner_id": owner_id, "exp": int(time.time()) + ttl_seconds}
    payload_b64 = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = _sign(payload_b64)
    return f"{payload_b64}.{signature}"


def parse_owner_token(token: str) -> str | None:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(_sign(payload_b64), signature):
        return None
    try:
        payload = json.loads(_b64decode(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    owner_id = payload.get("owner_id")
    return owner_id if isinstance(owner_id, str) and owner_id else None


def _sign(payload_b64: str) -> str:
    digest = hmac.new(settings.auth_secret.encode(), payload_b64.encode(), hashlib.sha256).digest()
    return _b64(digest)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
