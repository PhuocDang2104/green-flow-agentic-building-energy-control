"""Upload static media (CCTV demo clips, …) into MinIO object storage.

Idempotent: re-uploads overwrite the same keys. Run inside the api container
(it mounts ./data at /app/data and can reach the `minio` service):

  docker compose exec -T api python /app/scripts/upload_media.py

Keys: cctv/<file>.webm  -> served to the browser via /api/media/cctv/<file>.webm
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from greenflow.storage import objectstore  # noqa: E402

# In the container the repo data dir is mounted at /app/data; locally fall back
# to the repo path.
CCTV_DIRS = [Path("/app/data/cctv_samples/clips"), ROOT / "data" / "cctv_samples" / "clips"]


def main() -> None:
    objectstore.ensure_bucket()
    cctv_dir = next((d for d in CCTV_DIRS if d.is_dir()), None)
    if cctv_dir is None:
        print("no cctv clips dir found; skipping")
        return
    n = 0
    for clip in sorted(cctv_dir.glob("*.webm")):
        key = f"cctv/{clip.name}"
        objectstore.put_file(key, clip, "video/webm")
        print(f"uploaded {key} ({clip.stat().st_size // 1024} KB)")
        n += 1
    print(f"done: {n} clip(s) in bucket '{objectstore._bucket()}'")


if __name__ == "__main__":
    main()
