FROM node:22-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend ./
ENV VITE_API_BASE_URL=
RUN npm run build


FROM python:3.12-slim

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    QUANT_DATABASE_URL="sqlite:////data/quant_platform.db" \
    QUANT_STATIC_DIR="/app/static" \
    QUANT_DEFAULT_OWNER_ID="default" \
    QUANT_MARKET_DATA_PROVIDER="finance_data_reader"

RUN pip install --no-cache-dir uv==0.11.2 && mkdir -p /data

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/app ./app
COPY --from=frontend-build /frontend/dist ./static

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
