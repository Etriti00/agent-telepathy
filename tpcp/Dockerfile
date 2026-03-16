# TPCP A-DNS Relay Server
# Usage: docker build -t tpcp-relay . && docker run -p 8765:8765 tpcp-relay

FROM python:3.11-slim

WORKDIR /app

# Pull latest security patches from upstream Debian
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Copy and install package (core only, no dev/edge extras needed for relay)
COPY pyproject.toml README.md ./
COPY tpcp/ ./tpcp/

RUN pip install --no-cache-dir --upgrade pip wheel jaraco.context && \
    pip install --no-cache-dir -e . && \
    useradd -r -u 1001 -g root tpcp

USER tpcp

EXPOSE 8765

ENV TPCP_PORT=8765

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import socket; s=socket.socket(); s.connect(('127.0.0.1',8765)); s.close()" || exit 1

# Run the A-DNS relay server
CMD ["python", "-m", "tpcp.relay.server"]
