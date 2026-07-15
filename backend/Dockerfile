FROM python:3.12-slim

WORKDIR /app

# System deps + security scanning tools (nmap). subfinder & nuclei installed from binaries.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev nmap curl unzip ca-certificates libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install subfinder and nuclei (ProjectDiscovery) from prebuilt release binaries
ARG SUBFINDER_VERSION=2.6.6
ARG NUCLEI_VERSION=3.3.7
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) pd_arch="amd64" ;; \
      arm64) pd_arch="arm64" ;; \
      *) pd_arch="amd64" ;; \
    esac; \
    curl -sSL -o /tmp/subfinder.zip "https://github.com/projectdiscovery/subfinder/releases/download/v${SUBFINDER_VERSION}/subfinder_${SUBFINDER_VERSION}_linux_${pd_arch}.zip"; \
    unzip -o /tmp/subfinder.zip -d /usr/local/bin subfinder; \
    curl -sSL -o /tmp/nuclei.zip "https://github.com/projectdiscovery/nuclei/releases/download/v${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION}_linux_${pd_arch}.zip"; \
    unzip -o /tmp/nuclei.zip -d /usr/local/bin nuclei; \
    chmod +x /usr/local/bin/subfinder /usr/local/bin/nuclei; \
    rm -f /tmp/subfinder.zip /tmp/nuclei.zip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads reports data && chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["api"]
