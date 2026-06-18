FROM python:3.12-slim AS base

WORKDIR /app

# Copy source and install
COPY pyproject.toml ./
COPY hausly/ ./hausly/
RUN pip install --no-cache-dir .

# Copy remaining files (migrations, scripts, etc.)
COPY . .

# Development target
FROM base AS dev
RUN pip install --no-cache-dir ".[dev]"
CMD ["uvicorn", "hausly.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

# Production target
FROM base AS prod
CMD ["uvicorn", "hausly.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
