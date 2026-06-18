"""Object storage (MinIO, S3-compatible) cho ảnh / video / PDF report.

MinIO chạy nội bộ (service `minio`, không expose ra ngoài). Browser KHÔNG nói
chuyện trực tiếp với MinIO — object được phục vụ qua API proxy `/api/media/{key}`
(api/routers/media.py), nên không cần expose MinIO/presigned URL công khai và
không phải sửa Caddy của hệ thống khác trên VM dùng chung.

Key quy ước theo "thư mục ảo": reports/<file>.pdf, cctv/<file>.webm,
images/<file>.png ... Lazy client + ensure_bucket idempotent.
"""
from __future__ import annotations

import io
import mimetypes
from functools import lru_cache
from pathlib import Path

from ..config import get_settings


@lru_cache(maxsize=1)
def _client():
    """MinIO client (lazy, cache 1 lần)."""
    from minio import Minio
    s = get_settings()
    return Minio(s.s3_endpoint, access_key=s.s3_access_key,
                 secret_key=s.s3_secret_key, secure=s.s3_secure)


def _bucket() -> str:
    return get_settings().s3_bucket


def ensure_bucket() -> str:
    """Tạo bucket nếu chưa có (idempotent). Trả tên bucket."""
    c, b = _client(), _bucket()
    if not c.bucket_exists(b):
        c.make_bucket(b)
    return b


def guess_type(key: str) -> str:
    return mimetypes.guess_type(key)[0] or "application/octet-stream"


def put_file(key: str, path: str | Path, content_type: str | None = None) -> str:
    """Upload 1 file lên bucket dưới `key`. Trả về key."""
    ensure_bucket()
    _client().fput_object(_bucket(), key, str(path),
                          content_type=content_type or guess_type(key))
    return key


def put_bytes(key: str, data: bytes, content_type: str | None = None) -> str:
    ensure_bucket()
    _client().put_object(_bucket(), key, io.BytesIO(data), length=len(data),
                         content_type=content_type or guess_type(key))
    return key


def exists(key: str) -> bool:
    from minio.error import S3Error
    try:
        _client().stat_object(_bucket(), key)
        return True
    except S3Error:
        return False


def stat(key: str):
    """object stat (content_type, size...) — raise S3Error nếu không có."""
    return _client().stat_object(_bucket(), key)


def get_stream(key: str):
    """urllib3 response stream cho object; caller phải close()/release_conn()."""
    return _client().get_object(_bucket(), key)
