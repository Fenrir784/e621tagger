# Configuration Reference

This document provides comprehensive reference for all environment variables and configuration options used by e621tagger. It serves as a quick reference for deployment and DevOps agents.

---

## Environment Variables

### Application Configuration

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `MODEL_PATH` | `models/jtp-3-hydra.safetensors` | No | Path to model file |
| `TAGS_PATH` | `data/jtp-3-hydra-tags.csv` | No | Path to tag metadata CSV |
| `DEVICE` | `cuda` (if available, else `cpu`) | No | PyTorch device |
| `MAX_SEQ_LEN` | `1024` | No | Maximum sequence length |
| `APP_VERSION` | `test` | No | Application version string |

### File Handling

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `SAVE_UPLOADS` | `false` | No | Save uploaded images to disk |
| `UPLOAD_DIR` | `/app/uploads` | No | Directory for saved uploads |

### Server Configuration

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `USE_PROXY` | `false` | No | Trust reverse proxy headers |
| `GUNICORN_WORKERS` | `1` | No | Number of Gunicorn workers |
| `GUNICORN_TIMEOUT` | `120` | No | Worker timeout in seconds |

---

## Variable Details

### MODEL_PATH

Path to the JTP-3 Hydra model file.

```bash
# Default
MODEL_PATH=models/jtp-3-hydra.safetensors

# Custom location
MODEL_PATH=/models/custom-model.safetensors
```

**Note**: Model files are loaded on startup. The model is stored in memory during runtime.

### TAGS_PATH

Path to the tag metadata CSV file with categories and implications.

```bash
# Default
TAGS_PATH=data/jtp-3-hydra-tags.csv

# Custom metadata
TAGS_PATH=/data/custom-tags.csv
```

**Format**:
```csv
tag,category,implications
female,0,
anthro,5,
futanari,0,female male
```

### DEVICE

PyTorch device for model inference.

```bash
# Auto-detect (CUDA if available)
DEVICE=cuda

# Force CPU
DEVICE=cpu

# Specific GPU
DEVICE=cuda:0
DEVICE=cuda:1
```

**Behavior**:
- If `cuda` and CUDA available: Use GPU
- If `cpu` or no CUDA: Use CPU
- On CPU: Model converted to float32
- On GPU: Model in bfloat16

### MAX_SEQ_LEN

Maximum sequence length for image patch processing.

```bash
# Default (1024 patches)
MAX_SEQ_LEN=1024

# Lower for smaller images
MAX_SEQ_LEN=512

# Higher for larger images
MAX_SEQ_LEN=2048
```

**Constraints**: Must be between 64 and 2048.

**Effect**: Limits maximum image size. A 16x16 patch = 1 sequence token. With 1024 max:
- ~1024 patches max
- ~32×32 patches = 1024
- For 16px patches: 1024 × 16 = 16384px max dimension (theoretical)
- Practically: ~4096×4096 images fit in sequence constraint

### APP_VERSION

Application version string for display and caching.

```bash
# Development
APP_VERSION=test

# PR build
APP_VERSION=test-a1b2c3d

# Release
APP_VERSION=v123
```

**Usage**:
- Displayed in UI footer
- Service worker cache versioning
- Health check response

### SAVE_UPLOADS

Whether to save uploaded images to disk.

```bash
# Default (don't save)
SAVE_UPLOADS=false

# Save uploads
SAVE_UPLOADS=true
```

**When enabled**:
- Images saved to `UPLOAD_DIR`
- Filename: `{date}_{original_filename}`
- Path traversal protection enabled

### UPLOAD_DIR

Directory for saved uploads.

```bash
# Default
UPLOAD_DIR=/app/uploads

# Custom directory
UPLOAD_DIR=/data/uploads
```

### USE_PROXY

Trust reverse proxy headers for client IP detection.

```bash
# Default (don't trust)
USE_PROXY=false

# Trust proxy headers
USE_PROXY=true
```

**When enabled**:
- Uses `ProxyFix` middleware
- Trusts `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host`, `X-Forwarded-Prefix`
- Required when behind Traefik, nginx, etc.

### GUNICORN_WORKERS

Number of Gunicorn worker processes.

> **Important:** `GUNICORN_WORKERS` and `GUNICORN_TIMEOUT` are set as environment variables in the Docker container, but they are **NOT read by `app.py`**. Instead, they are passed to Gunicorn via shell substitution in the Docker CMD. The Dockerfile uses: `CMD ["sh", "-c", "gunicorn --workers ${GUNICORN_WORKERS} --timeout ${GUNICORN_TIMEOUT} app:app"]`

When you set these in docker-compose.yml:
```yaml
environment:
  - GUNICORN_WORKERS=2
  - GUNICORN_TIMEOUT=120
```
These values are available to the shell which runs the Gunicorn command.

```bash
# In Dockerfile, these are set as ENV and used in CMD:
ENV GUNICORN_WORKERS=1
ENV GUNICORN_TIMEOUT=120
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:5000 --workers ${GUNICORN_WORKERS} --timeout ${GUNICORN_TIMEOUT} app:app"]

# Using docker-compose, override the command:
command: gunicorn -w 2 --timeout 120 -b 0.0.0.0:5000 app:app

# Or pass as environment variables (they work because CMD uses shell substitution):
environment:
  - GUNICORN_WORKERS=2
  - GUNICORN_TIMEOUT=120
```

```bash
# Default (single worker)
GUNICORN_WORKERS=1

# Multiple workers
GUNICORN_WORKERS=2
GUNICORN_WORKERS=4
```

**Recommendation**:
- 1 worker: Development/single user
- 2+ workers: Production with load balancer
- Each worker loads model into memory

**Memory Impact**: Each additional worker adds ~2GB (model size)

### GUNICORN_TIMEOUT

Worker timeout before restart (in seconds).

> **Important:** Same as `GUNICORN_WORKERS`, these values are passed to Gunicorn via shell substitution in the Docker CMD, not read by app.py.

```bash
# Default (120 seconds)
GUNICORN_TIMEOUT=120

# Longer timeout
GUNICORN_TIMEOUT=300

# Shorter (faster recovery on issues)
GUNICORN_TIMEOUT=60
```

> **Why this works:** The Dockerfile uses shell substitution: `CMD ["sh", "-c", "gunicorn ... --workers ${GUNICORN_WORKERS} --timeout ${GUNICORN_TIMEOUT} ...]`. The ENV variables are interpolated by the shell before being passed to Gunicorn.

---

## Docker Configuration

### Environment Variables in Docker

```yaml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    environment:
      - SAVE_UPLOADS=false        # Don't save uploads
      - USE_PROXY=true            # Trust reverse proxy
      - GUNICORN_WORKERS=2        # 2 workers
      - GUNICORN_TIMEOUT=120     # 2 min timeout
    volumes:
      - ./uploads:/app/uploads  # Mount point
    ports:
      - "5000:5000"
```

---

## Runtime Detection

### Automatic Settings

The application automatically detects:

| Variable | Detection Method |
|----------|------------------|
| `DEVICE` | `torch.cuda.is_available()` |
| `APP_VERSION` | Git commit (in Docker) or `test` |

### Version Detection (in Docker)

The Docker workflow sets:
- PR builds: `test-{commit_sha}`
- Merged to latest: `v{pr_number}`

---

## Configuration Precedence

Precedence order (highest first):

1. Environment variables (override all)
2. Dockerfile defaults
3. Hardcoded Python defaults

Example in `app.py`:

```python
MODEL_PATH = os.getenv('MODEL_PATH', 'models/jtp-3-hydra.safetensors')
DEVICE = os.getenv('DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')
MAX_SEQ_LEN = int(os.getenv('MAX_SEQ_LEN', '1024'))
```

---

## Production Configuration

### Recommended Settings

For production deployment:

```yaml
environment:
  - SAVE_UPLOADS=true                         # Audit trail
  - USE_PROXY=true                            # Behind reverse proxy
  - GUNICORN_WORKERS=2                       # Redundancy
  - GUNICORN_TIMEOUT=120                  # 2 min timeout
```

### High-Traffic Settings

```yaml
environment:
  - SAVE_UPLOADS=false                      # Better performance
  - USE_PROXY=true
  - GUNICORN_WORKERS=4                     # Higher parallelism
  - GUNICORN_TIMEOUT=180                  # Longer for large images
```

---

## Development Configuration

For local development:

```bash
# .env file
MODEL_PATH=models/jtp-3-hydra.safetensors
DEVICE=cpu
MAX_SEQ_LEN=1024
SAVE_UPLOADS=false
USE_PROXY=false
APP_VERSION=dev
```

---

## Model Files

### Expected Structure

```
/app/
├── models/
│   └── jtp-3-hydra.safetensors
├── data/
│   └── jtp-3-hydra-tags.csv
├── extensions/
│   └── (optional extension files)
└── uploads/                    # Created if SAVE_UPLOADS=true
    └── (saved images)
```

---

## Health Check Response

The `/health` endpoint returns configuration info:

```json
{
  "status": "healthy",
  "model": "loaded",
  "tags_count": 7500,
  "version": "v123"
}
```

---

## Logging Configuration

### Log Level

Log level is set based on `APP_VERSION`:

```python
# test-* versions: DEBUG
# Others: INFO
LOG_LEVEL = logging.DEBUG if APP_VERSION.startswith('test-') else logging.INFO
```

### Log Format

```
2024-01-01 12:00:00 [INFO] 🚀 e621tagger version: v123
2024-01-01 12:00:00 [INFO] ⚙️ Loading e621tagger model on cuda...
2024-01-01 12:00:01 [INFO] ✅ Model loaded, 7500 tags
2024-01-01 12:00:01 [INFO] 📚 Loading tag metadata...
2024-01-01 12:00:01 [INFO] ✅ Metadata loaded, 7500 entries
2024-01-01 12:00:01 [INFO] ⏱️ Worker ready in 1500ms
```

---

## Rate Limiting Configuration

Rate limits are hardcoded in `app.py`:

```python
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["500 per hour"],
    storage_uri="memory://",
)

@app.route('/predict', methods=['POST'])
@limiter.limit("20 per minute")
def predict():
    ...
```

| Limit | Scope | Description |
|-------|-------|-------------|
| 500/hour | Default | Global per IP |
| 20/minute | /predict | Prediction endpoint |

---

## Security Constants

These are hardcoded and not configurable:

```python
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff'}
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB
```

| Constant | Value |
|----------|-------|
| Max file size | 20MB |
| Allowed formats | JPEG, PNG, GIF, WebP, BMP, TIFF |

---

## Checking Configuration

### Via Health Endpoint

```bash
curl https://tagger.fenrir784.ru/health

# Response includes tags_count (from loaded model)
```

### Via Logs

```bash
# Check container logs
docker logs e621tagger

# Look for version output
grep "e621tagger version" logs
```

---

## Extension Configuration

### Loading Extensions

Extensions are discovered automatically:

```python
# model.py
def discover_extensions(paths):
    for path in paths:
        if os.path.isdir(path):
            for entry in os.scandir(path):
                if entry.is_file() and entry.name.endswith('.safetensors'):
                    yield entry.path
```

### Default Extension Path

```python
# inference.py
default_extension = _if_exists("extensions/jtp-3-hydra")
```

---

## Full Example

### docker-compose.yml

```yaml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    container_name: e621tagger
    ports:
      - "5000:5000"
    environment:
      - SAVE_UPLOADS=true
      - USE_PROXY=true
      - GUNICORN_WORKERS=2
      - GUNICORN_TIMEOUT=120
    volumes:
      - ./uploads:/app/uploads
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 6G
          cpus: 12
```