FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY backend/greenflow ./backend/greenflow
RUN pip install --no-cache-dir -e .

COPY scripts ./scripts
COPY db ./db

ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "greenflow.api.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
