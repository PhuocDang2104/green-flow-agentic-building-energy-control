FROM python:3.11-slim

WORKDIR /app

# libgomp1: OpenMP runtime required by lightgbm's native lib (the [ml] surrogate
# forecast). python:3.11-slim omits it, so without this lightgbm import fails with
# "libgomp.so.1: cannot open shared object file" and the surrogate silently falls
# back to heuristics.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ---- Dependencies layer (keyed on pyproject.toml only) ----
# Changing app code / model files BELOW must NOT re-trigger these heavy downloads
# (torch ~190MB from the flaky pytorch index, + sentence-transformers/lightgbm).
# A stub greenflow package lets the editable install resolve+install deps before
# the real source exists; setuptools' editable path-finder then picks up the real
# source copied afterwards at runtime.
#   - CPU-only torch from PyTorch's CPU index (avoids the ~2GB CUDA build).
#   - [ml] = lightgbm + numpy + pandas (EnergyPlus-DoE / real surrogate).
#   - [embeddings] = sentence-transformers (BGE-M3 + bge-reranker-v2-m3, hybrid RAG).
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && mkdir -p backend/greenflow && touch backend/greenflow/__init__.py \
    && pip install --no-cache-dir -e ".[ml,embeddings]"

# ---- App source (changes here don't invalidate the deps layer above) ----
COPY backend/greenflow ./backend/greenflow
COPY scripts ./scripts
COPY db ./db

ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "greenflow.api.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
