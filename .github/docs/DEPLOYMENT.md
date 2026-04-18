# Deployment Guide

This document provides comprehensive deployment guidance for e621tagger. It covers Docker setup, self-hosting, and production configurations for DevOps agents.

---

## Quick Start

### Run with Docker

```bash
# Pull and run
docker run -p 5000:5000 ghcr.io/fenrir784/e621tagger:latest

# Access at http://localhost:5000
```

### Run with Docker Compose

```yaml
# docker-compose.yml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    ports:
      - "5000:5000"

docker compose up -d
```

---

## Docker Image

### Image Details

| Attribute | Value |
|----------|-------|
| Registry | `ghcr.io` |
| Organization | `fenrir784` |
| Repository | `e621tagger` |
| Tags | `latest`, `test`, `v{N}` |

### Image Tags

```bash
# Latest stable
docker pull ghcr.io/fenrir784/e621tagger:latest

# Latest test build
docker pull ghcr.io/fenrir784/e621tagger:test

# Specific version
docker pull ghcr.io/fenrir784/e621tagger:v123
```

### Architecture

| Architecture | Support |
|-------------|---------|
| linux/amd64 | Full |
| linux/arm64 | Full |

---

## Docker Setup

### Minimal Configuration

```yaml
# docker-compose.yml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    container_name: e621tagger
    ports:
      - "5000:5000"
    restart: unless-stopped
```

### Production Configuration

```yaml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    container_name: e621tagger
    ports:
      - "5000:5000"
    environment:
      - TZ=Europe/Moscow
      - SAVE_UPLOADS=true
      - USE_PROXY=true
    command: gunicorn -w 2 --timeout 120 -b 0.0.0.0:5000 app:app
    volumes:
      - ./uploads:/app/uploads
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 6G
          cpus: 12
```

> **Note:** `GUNICORN_WORKERS` and `GUNICORN_TIMEOUT` are passed to Gunicorn via command-line arguments (not as environment variables). The default Docker image uses shell substitution to interpolate these values. See [CONFIG.md](CONFIG.md) for details.

---

## Hardware Requirements

### Minimum (CPU)

| Resource | Requirement |
|----------|-------------|
| RAM | 4GB |
| CPU | 4 cores |
| Storage | 10GB |

### Recommended (GPU)

| Resource | Requirement |
|----------|-------------|
| RAM | 8GB |
| GPU | 4GB VRAM |
| CPU | 4 cores |
| Storage | 20GB |

### High Performance

| Resource | Requirement |
|----------|-------------|
| RAM | 16GB |
| GPU | 8GB+ VRAM (RTX 3090/4090) |
| CPU | 8+ cores |
| Storage | 50GB+ |

---

## Network Configuration

### Direct Access

```yaml
ports:
  - "5000:5000"
```

### Behind Reverse Proxy (Traefik)

```yaml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    environment:
      - USE_PROXY=true
    labels:
      - traefik.enable=true
      - traefik.http.routers.tagger.rule=Host(`tagger.example.com`)
      - traefik.http.routers.tagger.entrypoints=websecure
      - traefik.http.routers.tagger.tls.certresolver=letsencrypt
    expose:
      - 5000
```

### Nginx Configuration

```nginx
server {
    server_name tagger.example.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Set in container:
```yaml
environment:
  - USE_PROXY=true
```

---

## TLS/SSL Configuration

### Using Traefik

```yaml
labels:
  - traefik.http.routers.tagger.tls.certresolver=letsencrypt
```

### Using Nginx (Let's Encrypt)

```nginx
server {
    listen 443 ssl http2;
    server_name tagger.example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:5000;
        # ... proxy headers
    }
}
```

---

## Uploads Storage

### Enable Upload Saving

```yaml
environment:
  - SAVE_UPLOADS=true

volumes:
  - ./uploads:/app/uploads
```

### Upload Directory Structure

```
uploads/
├── 2024-01-01_image.png
├── 2024-01-02_artwork.png
└── 2024-01-03_furry_art.png
```

**Filename Format**: `{date}_{original_filename}`

### Cleanup Cron

```bash
# Add to crontab
0 0 * * * find /path/to/uploads -mtime +30 -delete
```

---

## Resource Limits

### Memory Limit

```yaml
deploy:
  resources:
    limits:
      memory: 6G
```

### CPU Limit

```yaml
deploy:
  resources:
    limits:
      cpus: 12
```

---

## Health Checks

### Docker Healthcheck

The container runs a health check internally. Use:

```bash
docker inspect e621tagger --format='{{.State.Health.Status}}'
```

### Manual Health Check

```bash
curl http://localhost:5000/health

# Response:
# {"status": "healthy", "model": "loaded", "tags_count": 7500, "version": "v123"}
```

---

## Logging

### Container Logs

```bash
# All logs
docker logs e621tagger

# Follow
docker logs -f e621tagger

# Last 100 lines
docker logs --tail 100 e621tagger
```

### Log Level

- `test-*` versions: DEBUG level
- Production: INFO level

---

## Updates

### Manual Update

```bash
# Pull latest
docker pull ghcr.io/fenrir784/e621tagger:latest

# Recreate container
docker compose up -d
```

### Watchtower (Automated)

```yaml
services:
  watchtower:
    image: containrrr/watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - WATCHTOWER_SCHEDULE=0 2 * * *
      - WATCHTOWER_CLEANUP=true
    command: --interval 86400
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs e621tagger

# Check status
docker inspect e621tagger
```

### Out of Memory

```yaml
deploy:
  resources:
    limits:
      memory: 8G  # Increase
```

### Slow Performance

```bash
# Check GPU usage
docker exec e621tagger nvidia-smi

# Check resources
docker stats
```

### Port Conflict

```yaml
ports:
  - "5001:5000"  # Use different host port
```

---

## Build from Source

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p models data uploads

EXPOSE 5000

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "app:app"]
```

### Build

```bash
docker build -t e621tagger:local .
docker run -p 5000:5000 e621tagger:local
```

---

## Multi-Container Setup

### With Traefik

```yaml
services:
  traefik:
    image: traefik:v3
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./traefik.yml:/traefik.yml:ro
    command: --configFile=/traefik.yml

  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    environment:
      - USE_PROXY=true
    expose:
      - 5000
```

---

## Database (Not Required)

e621tagger does not require a database. All state is in-memory.

---

## Backup

### What to Back Up

| Data | Location | Priority |
|------|----------|----------|
| Uploaded images | `./uploads/` | Optional |
| Configuration | `docker-compose.yml` | Required |

---

## Security

### Recommendations

1. **Don't expose port publicly without TLS**
2. **Rate limiting is per-IP**
3. **Consider container isolation**
4. **Keep images updated**

### Firewall

```bash
# UFW example
ufw allow 5000/tcp
ufw allow 443/tcp
ufw allow 80/tcp
```

---

## Performance Tuning

### Gunicorn Workers

| Users | Workers |
|-------|---------|
| Single | 1 |
| 1-10 | 2 |
| 10+ | 4+ |

**Important**: Each Gunicorn worker loads its own copy of the model into memory. With 7500+ tags, each worker uses ~2GB just for the model weights.

| Workers | Model Memory | Recommended GPU Memory |
|---------|-------------|---------------------|
| 1 | ~2GB | 4GB |
| 2 | ~4GB | 6GB |
| 4 | ~8GB | 12GB |

For single-user or low-traffic deployments, stick with 1 worker. Use multiple workers only if you need redundancy (worker restarts won't take down the service).

### GPU Inference

```yaml
environment:
  - DEVICE=cuda
```

---

## Container Health Monitoring

### Prometheus (External)

```bash
# Check health
curl http://localhost:5000/health
```

### Monitoring Tools

```yaml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
```

---

## Complete Production Example

```yaml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    container_name: e621tagger
    restart: unless-stopped
    ports:
      - "127.0.0.1:5000:5000"
    environment:
      - TZ=UTC
      - SAVE_UPLOADS=true
      - USE_PROXY=true
      - GUNICORN_WORKERS=2
      - GUNICORN_TIMEOUT=120
    volumes:
      - ./uploads:/app/uploads
    deploy:
      resources:
        limits:
          memory: 6G
          cpus: 8
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  watchtower:
    image: containrrr/watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 86400 --cleanup
```

---

## Cloud Deployment

### AWS ECS

```json
{
  "family": "e621tagger",
  "containerDefinitions": [
    {
      "name": "e621tagger",
      "image": "ghcr.io/fenrir784/e621tagger:latest",
      "memory": 4096,
      "portMappings": [
        {"containerPort": 5000}
      ],
      "environment": [
        {"name": "DEVICE", "value": "cuda"}
      ]
    }
  ]
}
```

### GCP Cloud Run

```yaml
# cloudbuild.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'ghcr.io/fenrir784/e621tagger:latest']
  - name: 'gcr.io/google-cloud-builders/gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'e621tagger'
      - '--image=ghcr.io/fenrir784/e621tagger:latest'
      - '--platform=managed'
      - '--region=us-central1'
```

---

## Verification

### After Deployment

```bash
# 1. Check health
curl http://localhost:5000/health

# 2. Test tagging
curl -X POST -F "image=@test.png" http://localhost:5000/predict

# 3. Check logs
docker logs e621tagger
```

---

## Support

- GitHub Issues: https://github.com/Fenrir784/e621tagger/issues
- Telegram: https://t.me/fenrir784