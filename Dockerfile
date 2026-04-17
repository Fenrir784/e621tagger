FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-cache-dir -r requirements.txt

# Uncomment and delete copy models and data if building locally
#ADD https://huggingface.co/RedRocket/JTP-3/resolve/main/models/jtp-3-hydra.safetensors models/jtp-3-hydra.safetensors
#ADD https://huggingface.co/RedRocket/JTP-3/resolve/main/data/jtp-3-hydra-tags.csv data/jtp-3-hydra-tags.csv

COPY models/ ./models/
COPY data/ ./data/

COPY *.py ./
COPY templates/ ./templates/
COPY static/ ./static/

ARG APP_VERSION=test
ENV APP_VERSION=${APP_VERSION}
ENV GUNICORN_WORKERS=1
ENV GUNICORN_TIMEOUT=120

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

EXPOSE 5000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:5000 --workers ${GUNICORN_WORKERS} --timeout ${GUNICORN_TIMEOUT} app:app"]
