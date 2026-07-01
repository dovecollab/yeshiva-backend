FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install the lean server-only dependencies (no desktop GUI libs)
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

COPY . .

RUN mkdir -p uploads/photos

EXPOSE 8000

# Bind to the port the platform provides (Koyeb injects $PORT), default 8000.
# One worker keeps memory within the free instance (512 MB).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
