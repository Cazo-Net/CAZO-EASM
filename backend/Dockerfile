# Build from the repository root:  docker build -f backend/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

# System deps (nmap is used by the port scanners when present)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev curl ca-certificates libpq5 nmap \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN mkdir -p uploads reports data && chmod +x entrypoint.sh

EXPOSE 8000

# Modes: api (default), scan-worker, migrate. Railway/Compose pass the mode
# through their start command, e.g. "sh entrypoint.sh scan-worker".
CMD ["sh", "/app/entrypoint.sh", "api"]
