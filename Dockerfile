# LOCAL DEVELOPMENT ONLY. Not a production image.
#
# Runs as root, bakes the source into the image and has no secret handling.
# Production is deployed as a supervised gunicorn process on the host - see
# docs/operations/deployment.md.

FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN uv sync --locked --no-dev
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Create required directories with proper permissions
RUN mkdir -p instance uploads/cases && chmod 777 instance uploads/cases

# Expose port
EXPOSE 5001

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--timeout", "120", "--preload", "main:app"]
