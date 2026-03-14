# TPCP A-DNS Relay Server
# Usage: docker build -t tpcp-relay . && docker run -p 9000:9000 tpcp-relay

FROM python:3.11-slim

WORKDIR /app

# Copy and install package (core only, no dev/edge extras needed for relay)
COPY pyproject.toml README.md ./
COPY tpcp/ ./tpcp/

RUN pip install --no-cache-dir -e .

EXPOSE 9000

# Run the A-DNS relay server
CMD ["python", "-m", "tpcp.relay.server"]
