FROM python:3.11-slim

# Install uv and curl (for healthcheck)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Create non-root user with home directory
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (including dev for tests)
RUN uv sync --frozen

# Copy application source and tests
COPY src/ ./src/
COPY tests/ ./tests/
COPY scripts/ ./scripts/

RUN chmod +x ./scripts/start_api.sh

# Ensure appuser owns the app directory and home
RUN chown -R appuser:appuser /app /home/appuser

# Switch to non-root user
USER appuser
ENV UV_CACHE_DIR=/home/appuser/.cache/uv

CMD ["./scripts/start_api.sh"]
