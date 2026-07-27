FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev curl ca-certificates libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN mkdir -p uploads reports data

EXPOSE 8000

# Railway provides $PORT; uvicorn binds to it.
CMD ["sh", "-c", "python -c 'from app.database import init_db; init_db()' && python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
