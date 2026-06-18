"""Media proxy: stream objects from MinIO to the browser.

Browser fetches /api/media/{key} (vd /api/media/cctv/office_1.webm,
/api/media/reports/x.pdf); API kéo từ MinIO nội bộ rồi stream về -> MinIO không
cần expose ra ngoài, và URL luôn cùng origin với API (an toàn cho frontend Vercel
khác origin: chỉ cần prefix NEXT_PUBLIC_API_BASE).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ...storage import objectstore

router = APIRouter()


@router.get("/media/{key:path}")
def get_media(key: str):
    from minio.error import S3Error
    try:
        st = objectstore.stat(key)
    except S3Error:
        raise HTTPException(404, "object not found")
    except Exception as exc:  # noqa: BLE001 — MinIO down/misconfig -> 503 rõ ràng
        raise HTTPException(503, f"object storage unavailable: {exc}")

    resp = objectstore.get_stream(key)

    def _iter():
        try:
            for chunk in resp.stream(64 * 1024):
                yield chunk
        finally:
            resp.close()
            resp.release_conn()

    content_type = st.content_type or objectstore.guess_type(key)
    headers = {"Cache-Control": "public, max-age=3600"}
    if st.size is not None:
        headers["Content-Length"] = str(st.size)
    return StreamingResponse(_iter(), media_type=content_type, headers=headers)
