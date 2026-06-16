FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install uv

# 1. Copy requirements.txt while still root to install globally

COPY ./requirements.txt .


RUN pip install --no-cache-dir --upgrade -r requirements.txt


# 3. Create and switch to the non-root user
RUN useradd --create-home appuser && chown appuser:appuser /app
USER appuser

# 4. Copy application code with correct ownership
COPY --chown=appuser:appuser app/ app/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Since it's installed to the system, you call uvicorn directly
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]