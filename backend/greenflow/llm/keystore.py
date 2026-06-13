"""Mã hoá API key trước khi lưu DB (không lưu key trần).

Dùng Fernet (cryptography) với master secret từ env (LLM_KEYSTORE_SECRET). Khi
"select provider + nhập key + lưu": key được encrypt() rồi cất vào provider_configs;
lúc gọi LLM mới decrypt() trong bộ nhớ. Master secret KHÔNG nằm trong DB/Git.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def _fernet(secret: str) -> Fernet:
    # SHA256(secret) -> 32 byte -> urlsafe base64 = Fernet key
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def encrypt_key(plaintext: str, secret: str) -> str:
    return _fernet(secret).encrypt(plaintext.encode()).decode()


def decrypt_key(token: str, secret: str) -> str:
    return _fernet(secret).decrypt(token.encode()).decode()


def mask(plaintext: str) -> str:
    """Hiển thị an toàn: gsk_…CCqD0F."""
    if len(plaintext) <= 10:
        return "…"
    return f"{plaintext[:4]}…{plaintext[-6:]}"
