FROM python:3.11-slim

WORKDIR /app

# Build deps for psycopg2 native driver
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir "poetry==1.8.3"

# Copy dependency manifests first for layer caching
COPY pyproject.toml poetry.lock* ./

# Install production dependencies only (no virtualenv needed inside container)
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# Copy application code
COPY . .

# Run as non-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5050

# Flask-SocketIO requires eventlet worker; 1 worker only
CMD ["gunicorn", \
     "--config", "gunicorn.conf.py", \
     "run:app"]
