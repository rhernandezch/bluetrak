FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

COPY src/ src/

ENV BLUETRAK_DB_PATH=/data/bluetrak.db

VOLUME /data

CMD ["uv", "run", "bluetrak"]
