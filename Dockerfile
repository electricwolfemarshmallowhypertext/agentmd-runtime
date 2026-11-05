FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=on

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-cli.txt requirements-server.txt ./
RUN python -m pip install -r requirements-server.txt

COPY apps/api/src ./apps/api/src
COPY cli ./cli
COPY schemas ./schemas
COPY public ./public
COPY AGENTS.md agentmd.yaml ./
COPY skills ./skills
COPY memory ./memory
COPY policies ./policies
COPY evals ./evals

RUN useradd -u 10001 -m appuser \
    && mkdir -p /app/receipts /app/.agentmd /app/.sticky /data/memory \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1
CMD ["uvicorn", "apps.api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
