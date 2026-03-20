FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# Install dependencies in a cached layer — only re-runs when lockfile changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy source and complete the install
COPY src/ src/
RUN uv sync --frozen --no-dev

CMD ["uv", "run", "--no-sync", "bluetrak"]
