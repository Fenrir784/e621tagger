# Docker Compose Configuration

This document provides comprehensive documentation of the Docker Compose configurations for e621tagger. It covers production, test, and custom setups.

---

## Configuration Files

> **Note:** These files are located in the `.github/` directory (repository root), not within `.github/documentation/`.

| File | Purpose | Environment |
|------|---------|-------------|
| `.github/compose.yml` | Production | Production |
| `.github/compose-test.yml` | Test/Development | Test |

---

## Production Configuration

**File**: `.github/compose.yml`

```yaml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    container_name: e621tagger
    restart: unless-stopped
    pull_policy: always
    deploy:
      resources:
        limits:
          memory: 6G
          cpus: 12
    expose:
      - 5000
    networks:
      - lushway_web
    environment:
      - TZ=Europe/Moscow
      - SAVE_UPLOADS=true
      - USE_PROXY=true
      - GUNICORN_WORKERS=2
      - GUNICORN_TIMEOUT=120
    volumes:
      - /home/fenrir784/e621tagger-saved/uploads:/app/uploads
    labels:
      - traefik.enable=true
      - traefik.http.routers.tagger.rule=Host(`www.tagger.fenrir784.ru`)
      - traefik.http.routers.tagger.entrypoints=websecure

networks:
  lushway_web:
    external: true
```

---

## Test Configuration

**File**: `.github/compose-test.yml`

```yaml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:test
    container_name: e621tagger-test
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 6G
          cpus: 12
    ports:
      - 5001:5000
    environment:
      - TZ=Europe/Moscow
      - SAVE_UPLOADS=false
```

---

## Configuration Comparison

| Setting | Production | Test |
|---------|-----------|------|
| Image | `latest` | `test` |
| Container Name | `e621tagger` | `e621tagger-test` |
| Restart | `unless-stopped` | `unless-stopped` |
| Ports | Exposed via Traefik | `5001:5000` |
| Network | Traefik | Default |
| SAVE_UPLOADS | `true` | `false` |
| USE_PROXY | `true` | `false` |
| GUNICORN_WORKERS | 2 | (default 1) |
| Memory Limit | 6GB | 6GB |
| CPU Limit | 12 | 12 |

---

## Usage Examples

### Running Production Compose

```bash
# Create network first
docker network create lushway_web

# Start production
docker compose -f .github/compose.yml up -d

# Check status
docker compose -f .github/compose.yml ps
```

### Running Test Compose

```bash
# Start test
docker compose -f .github/compose-test.yml up -d

# Access test instance
curl http://localhost:5001/health
```

### Using Custom Values

```yaml
# custom.yml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    ports:
      - "5000:5000"
    environment:
      - TZ=UTC
      - SAVE_UPLOADS=true
      - USE_PROXY=false
      - DEVICE=cpu
    volumes:
      - ./data/uploads:/app/uploads
    restart: unless-stopped
```

```bash
docker compose -f custom.yml up -d
```

---

## Service Definitions

### Image

```yaml
image: ghcr.io/fenrir784/e621tagger:latest
```

| Tag | Description |
|-----|-------------|
| `latest` | Latest stable |
| `test` | Latest test build |
| `v123` | Specific version |

### Container Name

```yaml
container_name: e621tagger
```

**Purpose**: Stable identifier for logs and management.

---

## Restart Policy

```yaml
restart: unless-stopped
```

| Policy | Behavior |
|--------|----------|
| `no` | Never restart |
| `always` | Always restart |
| `on-failure` | Restart on error |
| `unless-stopped` | Restart unless manually stopped |

---

## Pull Policy

```yaml
pull_policy: always
```

| Policy | Behavior |
|--------|----------|
| `always` | Always pull image |
| `if-not-present` | Pull if not cached |
| `never` | Never pull |
| `default` | Use default |

---

## Resource Limits

```yaml
deploy:
  resources:
    limits:
      memory: 6G
      cpus: 12
```

### Recommended Settings

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| Memory | 4GB | 6-8GB |
| CPU | 4 cores | 8-12 cores |

---

## Networking

### Production Network

```yaml
networks:
  - lushway_web

networks:
  lushway_web:
    external: true
```

**Purpose**: Connect to Traefik reverse proxy network.

### Test/Development Network

No explicit network - uses default bridge.

### Port Mapping

```yaml
ports:
  - "5001:5000"
```

| Format | Host Port | Container Port |
|--------|----------|--------------|
| `"5000:5000"` | 5000 | 5000 |
| `"5001:5000"` | 5001 | 5000 |

---

## Environment Variables

### TZ (Timezone)

```yaml
- TZ=Europe/Moscow
```

Sets timezone for logging and file naming.

### SAVE_UPLOADS

```yaml
- SAVE_UPLOADS=true
```

| Value | Behavior |
|-------|----------|
| `true` | Save uploads to volume |
| `false` | Temp files only |

### USE_PROXY

```yaml
- USE_PROXY=true
```

| Value | Behavior |
|-------|----------|
| `true` | Trust reverse proxy |
| `false` | Use direct IP |

### GUNICORN_WORKERS

```yaml
- GUNICORN_WORKERS=2
```

Workers are independent processes. Each loads model (~2GB).

### GUNICORN_TIMEOUT

```yaml
- GUNICORN_TIMEOUT=120
```

Timeout before worker restart (seconds).

---

## Volume Mounts

### Uploads Directory

```yaml
volumes:
  - /home/fenrir784/e621tagger-saved/uploads:/app/uploads
```

| Host Path | Container Path | Purpose |
|----------|--------------|---------|
| `/path/on/host` | `/app/uploads` | Saved uploads |

### Bind Mount Example

```yaml
volumes:
  - ./uploads:/app/uploads
```

Creates `./uploads` directory on host.

---

## Labels (Traefik)

```yaml
labels:
  - traefik.enable=true
  - traefik.http.routers.tagger.rule=Host(`www.tagger.fenrir784.ru`)
  - traefik.http.routers.tagger.entrypoints=websecure
```

| Label | Purpose |
|-------|---------|
| `traefik.enable` | Enable Traefik routing |
| `traefik.http.routers.{name}.rule` | Host rule |
| `traefik.http.routers.{name}.entrypoints` | Entry point |

---

## Quick Start

### Production

```bash
# Create network
docker network create production

# Start
docker compose -f .github/compose.yml up -d

# View logs
docker logs -f e621tagger
```

### Test

```bash
# Start test
docker compose -f .github/compose-test.yml up -d

# Test
curl http://localhost:5001/health

# Stop
docker compose -f .github/compose-test.yml down
```

---

## Custom Compose Examples

### Minimal

```yaml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    ports:
      - "5000:5000"
```

### CPU-Only

```yaml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    environment:
      - DEVICE=cpu
    ports:
      - "5000:5000"
    deploy:
      resources:
        limits:
          memory: 4G
```

### With Uploads

```yaml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    environment:
      - SAVE_UPLOADS=true
    volumes:
      - ./uploads:/app/uploads
    ports:
      - "5000:5000"
```

### Behind Nginx

```yaml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    environment:
      - USE_PROXY=true
    expose:
      - 5000

  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
```

---

## Health Check

The container has an internal health check. Verify with:

```bash
# Docker inspect
docker inspect e621tagger --format='{{.State.Health.Status}}'

# API health check
curl http://localhost:5000/health
```

---

## Logging

```bash
# View all logs
docker logs e621tagger

# Follow logs
docker logs -f e621tagger

# Last 100 lines
docker logs --tail 100 e621tagger
```

---

## Updating

```bash
# Pull latest image
docker compose pull

# Recreate containers
docker compose up -d
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs e621tagger

# Check status
docker ps -a
```

### Port Already in Use

```yaml
# Change port
ports:
  - "5001:5000"
```

### Out of Memory

```yaml
# Increase memory
deploy:
  resources:
    limits:
      memory: 8G
```

---

## Complete Production Compose

```yaml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    container_name: e621tagger
    restart: unless-stopped
    pull_policy: always
    deploy:
      resources:
        limits:
          memory: 6G
          cpus: 12
    expose:
      - 5000
    networks:
      - production
    environment:
      - TZ=UTC
      - SAVE_UPLOADS=true
      - USE_PROXY=true
      - GUNICORN_WORKERS=2
      - GUNICORN_TIMEOUT=120
    volumes:
      - ./uploads:/app/uploads
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  production:
    driver: bridge
```

---

## Multi-Environment Setup

### Directory Structure

```
e621tagger/
├── .github/
│   ├── compose.yml           # Production
│   ├── compose-test.yml     # Test
│   ├── docker-compose.yml   # Local override
│   └── workflows/
└── uploads/
```

### Start Command

```bash
# Production
docker compose -f .github/compose.yml up -d

# Test
docker compose -f .github/compose-test.yml up -d

# Local development
docker compose up -d
```

---

## Integration

### With Watchtower

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

## Maintenance

### Backup Uploads

```bash
# Backup
tar -czf uploads-backup-$(date +%Y%m%d).tar.gz ./uploads

# Restore
tar -xzf uploads-backup-20240101.tar.gz
```

### Cleanup

```bash
# Remove stopped containers
docker compose rm

# Remove volumes (careful!)
docker compose down -v

# Prune images
docker system prune
```