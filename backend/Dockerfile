FROM python:3.12-slim

WORKDIR /app

# Pure-Python EASM scanner: no external CLI binaries (nmap/nuclei/subfinder/amass)
# are required. All scanning is done via stdlib + dnspython + httpx + cryptography.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev curl ca-certificates libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads reports data && chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["api"]
