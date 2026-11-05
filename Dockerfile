FROM python:3.12-slim

# git: ds-consumer-auth is installed from its GitHub tag
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY services/ services/
COPY static/ static/
COPY data/ data/

# One core per optimisation: numerical libraries must not spawn a thread per core
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    CACHE_DIR=/app/cache PYTHONUNBUFFERED=1

RUN useradd --uid 10001 --create-home app && mkdir -p /app/cache && chown app /app/cache
USER 10001

EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz')"]

# One worker process: data and jobs live in its memory. The optimisations run
# in child processes, one at a time (JOB_WORKERS).
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "--timeout", "120", "server:create_app()"]
