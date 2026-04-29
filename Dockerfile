# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install runtime dependencies first to keep this layer cacheable.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir gunicorn==22.0.0

# Copy the application source.
COPY . .

# Create and switch to an unprivileged user.
RUN useradd --create-home --shell /usr/sbin/nologin fairgame \
 && chown -R fairgame:fairgame /app
USER fairgame

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status==200 else 1)"

# Production server: uvicorn with multiple workers for concurrent LLM
# requests; long --timeout via UVICORN env vars / app code.
CMD ["uvicorn", "fairgame_web:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--log-level", "info"]
