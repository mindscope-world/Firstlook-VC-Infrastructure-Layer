# One image for every Python service; the command picks the process:
#   uvicorn firstlook_ingest.app:app | uvicorn firstlook_gateway.app:app
#   python -m firstlook_core.relay | firstlook_resolver.consumer | firstlook_ai.consumer
#   python -m firstlook_ingest.slack | firstlook_workflows.worker
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
COPY packages/pycore packages/pycore
COPY packages/fixtures packages/fixtures
COPY packages/schema packages/schema
COPY services/ingest services/ingest
COPY services/resolver services/resolver
COPY services/ai services/ai
COPY services/gateway services/gateway
COPY workflows workflows
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home app
WORKDIR /app
COPY --from=build --chown=app /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
CMD ["uvicorn", "firstlook_ingest.app:app", "--host", "0.0.0.0", "--port", "8080"]
