"""Self-hosted voice for the chat assistant — CPU only, no cloud.

STT: faster-whisper (base.en, int8) — decodes the browser's recording via the
bundled PyAV, so no system ffmpeg is needed. TTS: Piper (en_US-lessac-medium)
via its CLI (stable across versions). Models download once into the storage
volume, then are cached. Lazy-loaded so the API starts fast and only pays the
cost when voice is actually used.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from ...config import get_settings

router = APIRouter(prefix="/voice")


def _storage_root() -> Path:
    for p in Path(get_settings().vector_index_path).resolve().parents:
        if p.name == "storage":
            return p
    return Path("/app/storage")


MODELS = _storage_root() / "models"
WHISPER_DIR = MODELS / "whisper"
PIPER_DIR = MODELS / "piper"
PIPER_ONNX = PIPER_DIR / "en_US-lessac-medium.onnx"
PIPER_JSON = PIPER_DIR / "en_US-lessac-medium.onnx.json"
PIPER_URL = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/"
             "en/en_US/lessac/medium/")

_whisper = None


def _get_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel  # heavy import, lazy
        WHISPER_DIR.mkdir(parents=True, exist_ok=True)
        _whisper = WhisperModel("base.en", device="cpu", compute_type="int8",
                                download_root=str(WHISPER_DIR))
    return _whisper


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Speech → text. Accepts the browser's recorded audio (webm/ogg/wav)."""
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty audio")
    suffix = os.path.splitext(file.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        path = f.name
    try:
        segments, _ = _get_whisper().transcribe(path, language="en", beam_size=1)
        text = " ".join(s.text for s in segments).strip()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"transcription failed: {e}")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return {"text": text}


def _ensure_piper_voice() -> None:
    PIPER_DIR.mkdir(parents=True, exist_ok=True)
    for fn, url in ((PIPER_ONNX, PIPER_URL + "en_US-lessac-medium.onnx"),
                    (PIPER_JSON, PIPER_URL + "en_US-lessac-medium.onnx.json")):
        if fn.exists() and fn.stat().st_size > 0:
            continue
        tmp = fn.with_suffix(fn.suffix + ".part")
        with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
            r.raise_for_status()
            with open(tmp, "wb") as out:
                for chunk in r.iter_bytes():
                    out.write(chunk)
        tmp.rename(fn)  # atomic: a cancelled download leaves only .part, never a corrupt voice


# strip markdown so TTS doesn't read "asterisk asterisk"; collapse to one line
def _clean_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[*_`#>|]", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [label](url) -> label
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1200]


class SpeakRequest(BaseModel):
    text: str


@router.post("/speak")
def speak(req: SpeakRequest):
    """Text → speech (WAV)."""
    text = _clean_for_speech(req.text or "")
    if not text:
        raise HTTPException(400, "empty text")
    _ensure_piper_voice()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out_path = f.name
    try:
        proc = subprocess.run(
            ["piper", "--model", str(PIPER_ONNX), "--output_file", out_path],
            input=text.encode("utf-8"), capture_output=True, timeout=60)
        if proc.returncode != 0:
            raise HTTPException(500, f"tts failed: {proc.stderr.decode()[:200]}")
        audio = Path(out_path).read_bytes()
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass
    return Response(content=audio, media_type="audio/wav")
