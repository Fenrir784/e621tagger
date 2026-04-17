# e621tagger Documentation Index

Comprehensive documentation for agents working with the e621tagger codebase.

## Overview

e621tagger is a web-based tool that automatically generates relevant tags for furry artwork using the **JTP-3 Hydra** model by Project RedRocket. The system accepts image uploads, processes them through a deep learning model, and returns tag predictions with confidence scores.

## Documentation Map

| Document | Purpose | Audience | Key Topics |
|----------|---------|----------|------------|
| [APP.md](APP.md) | app.py reference, all methods/variables | Backend agents | Flask routes, endpoints, runtime |
| [JS.md](JS.md) | JavaScript reference, all functions/variables | Frontend agents | UI logic, event handlers, API calls |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System overview, component relationships, data flow | All agents | Layers, data flow, security |
| [API.md](API.md) | Flask endpoints, request/response contracts | API integration agents | Endpoints, rate limits, errors |
| [MODEL.md](MODEL.md) | JTP-3 Hydra architecture, NaFlexVit details | ML/inference agents | Model architecture, inference |
| [TAGGING.md](TAGGING.md) | Tag classification, implications, categories | Content handling agents | Categories, thresholds, output |
| [CONFIG.md](CONFIG.md) | Environment variables, configuration options | Deployment agents | Env vars, Docker, Gunicorn |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Docker setup, self-hosting guide | DevOps agents | Docker, compose, production |
| [CI_CD.md](CI_CD.md) | GitHub Actions workflow, CI/CD pipeline | CI/CD agents | Build, deploy, versioning |
| [COMPOSE.md](COMPOSE.md) | Docker Compose configurations | DevOps agents | Compose files, networking |
| [PWA.md](PWA.md) | Service worker, manifest, offline support | Frontend agents | PWA, caching, offline |
| [CSS.md](CSS.md) | Frontend styles, themes, responsive design | Frontend agents | Styling, themes, components |

## Quick Reference

### Core Endpoints

```
GET  /                    - Main UI page
POST /predict              - Image classification (rate limited: 20/min)
GET  /health              - Health check
GET  /service-worker.js   - PWA service worker
GET  /static/<path>       - Static assets
```

### Environment Variables

> **Note:** For `GUNICORN_WORKERS` and `GUNICORN_TIMEOUT`, see [CONFIG.md](CONFIG.md) - these are passed to Gunicorn via command-line arguments, not read as environment variables by app.py.

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PATH` | `models/jtp-3-hydra.safetensors` | Model file path |
| `TAGS_PATH` | `data/jtp-3-hydra-tags.csv` | Tag metadata CSV |
| `DEVICE` | `cuda` (fallback: `cpu`) | PyTorch device |
| `MAX_SEQ_LEN` | `1024` | Maximum sequence length |
| `APP_VERSION` | `test` | Application version |
| `SAVE_UPLOADS` | `false` | Save uploaded images |
| `UPLOAD_DIR` | `/app/uploads` | Upload save directory |
| `USE_PROXY` | `false` | Trust reverse proxy headers |

> **Note:** `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` is used internally in the CI/CD pipeline and does not need to be set for normal operation.

### Docker Image

```
ghcr.io/fenrir784/e621tagger:latest
```

### Key Files

| File | Purpose |
|------|---------|
| `app.py` | Flask application, API endpoints, rate limiting |
| `model.py` | Model loading, image processing, extension system |
| `inference.py` | CLI for batch classification, tag metadata |
| `hydra_pool.py` | Hydra attention pooling layer |
| `siglip2.py` | NaFlex Vision Transformer backbone |
| `image.py` | sRGB color management, patch extraction |
| `loader.py` | Multi-process image loading |

### Supported Image Formats

- JPEG, PNG, GIF, WebP, BMP, TIFF
- Maximum file size: 20MB

### Tag Categories

| ID | Category | Description |
|----|----------|-------------|
| 0 | General | General tags |
| 1 | Artist | Artist tags |
| 3 | Copyright | Copyright/series tags |
| 4 | Character | Character tags |
| 5 | Species | Species tags |
| 7 | Meta | Meta tags (rating, resolution) |
| 8 | Lore | Lore-related tags |
| - | Other | Tags from unrecognized categories |

## Common Tasks

### Run locally with Docker

```bash
docker run -p 5000:5000 ghcr.io/fenrir784/e621tagger:latest
```

### Query health endpoint

```bash
curl https://tagger.fenrir784.ru/health
```

### Submit image for tagging

```bash
curl -X POST -F "image=@image.png" https://tagger.fenrir784.ru/predict
```

## Model Information

- **Architecture**: naflexvit_so400m_patch16_siglip + HydraPool
- **Base Model**: SigLIP-400m
- **Tags**: ~7,500 (determined by model file)
- **Input**: Image patches (16x16)
- **Sequence Length**: Up to 1024 patches
- **Model Source**: HuggingFace `RedRocket/JTP-3`

> **Note:** The exact tag count depends on the model file loaded. The default model contains approximately 7,500 tags.

## Security Headers

The application sets the following security headers on all responses:

- `Strict-Transport-Security`: max-age=31536000
- `X-Frame-Options`: DENY
- `X-Content-Type-Options`: nosniff
- `Referrer-Policy`: strict-origin-when-cross-origin
- `Permissions-Policy`: geolocation=(), microphone=(), camera=()
- `Content-Security-Policy`: default-src 'self'; img-src 'self' data: blob:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://e621.net; object-src 'none'; base-uri 'self';

## Rate Limits

- `/predict`: 20 requests per minute (additional limit)
- All endpoints: 500 requests per hour (global default limit)
- Unauthenticated access only

> **Note:** The 500/hour limit applies to all endpoints. The `/predict` endpoint has an additional stricter limit of 20/minute.

## Support

- GitHub: https://github.com/Fenrir784/e621tagger
- Telegram: https://t.me/fenrir784
- Live Instance: https://tagger.fenrir784.ru