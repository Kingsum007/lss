"""Standard authenticated encryption; no custom cipher implementation."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITERATIONS = 600000
CHECK = b"LSS vault verification v1"
CHECK_AAD = b"LSS key-check v1"


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def unb64(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def aad(operation_id: str, schema: int = 1) -> bytes:
    return json.dumps([operation_id, schema], ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def derive_key(passphrase: str, salt: bytes, iterations: int = ITERATIONS) -> bytes:
    if not isinstance(passphrase, str) or len(passphrase) < 12:
        raise ValueError("Use a passphrase of at least 12 characters")
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations, dklen=32)


def create_vault(passphrase: str) -> tuple[bytes, dict]:
    salt = os.urandom(16)
    key = derive_key(passphrase, salt)
    iv = os.urandom(12)
    check = AESGCM(key).encrypt(iv, CHECK, CHECK_AAD)
    config = {"name": "vault", "version": 1, "keyVersion": str(uuid.uuid4()), "iterations": ITERATIONS,
              "salt": b64(salt), "checkIv": b64(iv), "check": b64(check)}
    return key, config


def unlock_vault(passphrase: str, config: dict) -> bytes:
    if config.get("version") != 1 or config.get("iterations") != ITERATIONS:
        raise ValueError("Unsupported vault configuration")
    try:
        key = derive_key(passphrase, unb64(config["salt"]), config["iterations"])
        if AESGCM(key).decrypt(unb64(config["checkIv"]), unb64(config["check"]), CHECK_AAD) != CHECK:
            raise ValueError()
        return key
    except Exception:
        raise ValueError("Cannot unlock: incorrect passphrase or damaged vault") from None


def encrypt_record(key: bytes, operation_id: str, payload: str, schema: int = 1) -> dict:
    iv = os.urandom(12)
    return {"iv": b64(iv), "ciphertext": AESGCM(key).encrypt(iv, payload.encode("utf-8"), aad(operation_id, schema))}


def decrypt_record(key: bytes, record: dict) -> str:
    return AESGCM(key).decrypt(unb64(record["iv"]), bytes(record["ciphertext"]), aad(record["id"], record["schema"])).decode("utf-8", errors="strict")
