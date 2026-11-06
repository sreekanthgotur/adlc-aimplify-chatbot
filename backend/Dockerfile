FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend/README.md backend/pyproject.toml backend/uv.lock /app/backend/
COPY backend/alembic.ini /app/backend/alembic.ini
COPY backend/alembic /app/backend/alembic
COPY backend/src /app/backend/src

RUN uv sync --project backend --frozen --no-dev \
    && useradd --system --uid 10001 --user-group --create-home app \
    && chown -R app:app /app

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health/live', timeout=2).read()"

CMD ["/app/backend/.venv/bin/uvicorn", "aimplify_intake.main:app", "--app-dir", "/app/backend/src", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
