# e621tagger Architecture

This document provides a comprehensive system overview for agent understanding. It describes component relationships, data flows, and the overall system architecture.

## System Overview

e621tagger is a Flask-based web application that provides automatic image tagging for furry artwork using the JTP-3 Hydra deep learning model. The system consists of three main layers:

1. **Web Layer** - Flask HTTP handling, security, rate limiting
2. **Inference Layer** - Image processing, model execution, tag prediction
3. **Model Layer** - JTP-3 Hydra architecture, NaFlexVit backbone

```
┌─────────────────────────────────────────────────────────┐
│                   Web Layer (Flask)                    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────────┐ │
│  │ HTTP    │  │ Rate    │  │ Security│  │ Template   │ │
│  │ Routes  │  │ Limiter │  │ Headers │  │ Rendering  │ │
│  └─────────┘  └─────────┘  └─────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                Inference Layer (app.py)                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ Image   │  │ Patch   │  │ Model   │  │ Tag     │ │
│  │ Upload │  │ Extract │  │ Inference│ │ Output  │ │
│  │ Handler│  │         │  │         │  │         │ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   Model Layer                          │
│  ┌─────────────────────────────────────────────────┐  │
│  │           JTP-3 Hydra Model                      │  │
│  │  ┌─────────────┐  ┌─────────────────────────┐  │  │
│  │  │ NaFlex ViT  │  │   HydraPool Head         │  │  │
│  │  │ Backbone   │  │   (7,500+ tags)          │  │  │
│  │  └─────────────┘  └─────────────────────────┘  │  │
│  └─────────────────────────────────────────────────┘  │
└──────────────────────────��──────────────────────────────┘
```

## Component Relationships

### Core Components

| Component | File | Responsibility |
|-----------|------|----------------|
| Flask App | `app.py` | HTTP routing, request handling, security |
| Model Loader | `model.py` | Model loading, image patch extraction |
| Inference | `inference.py` | CLI batch inference, metadata handling |
| HydraPool | `hydra_pool.py` | Attention-based classification head |
| NaFlexVit | `siglip2.py` | Vision Transformer backbone |
| Image Processor | `image.py` | sRGB conversion, patch creation |
| Loader | `loader.py` | Multi-process image loading for batching |

### Component Interaction Diagram

```
User Upload
    │
    ▼
┌────────────────┐
│  app.py         │
│  (Flask)        │
│                │
│  1. Validate   │
│  2. Save/Temp  │
│  3. Extract    │
└────────┬───────┘
         │
         ▼
┌────────────────┐
│  model.py       │
│                │
│  1. process_   │
│     image()     │
│  2. patchify_  │
│     image()    │
└────────┬───────┘
         │
    patches, patch_coords,
    patch_valid
         │
         ▼
┌────────────────┐
│  NaFlexVit      │
│  (siglip2.py)  │
│                │
│  1. embeds()   │
│  2. blocks[]   │
│  3. norm()     │
│  4. forward_   │
│    head()      │
└────────┬───────┘
         │
    image_features
         │
         ▼
┌────────────────┐
│  HydraPool     │
│  (hydra_pool) │
│               │
│  1. attn()    │
│  2. ff()      │
│  3. out_proj()│
└────────┬───────┘
         │
    logits (7500+)
         │
         ▼
┌────────────────┐
│  Top-K Filter  │
│  + Metadata   │
│  + Auto Tags │
│  = Response  │
└──────────────┘
```

## Data Flow

### Image Classification Flow

```
1. Upload Phase
   User → POST /predict → Flask validates file (type, size)
   │
2. Preprocessing Phase
   PIL Image.open() → process_srgb() → resize to sequence limit
   → patchify_image() → patches, patch_coords, patch_valid tensors
   │
3. Model Inference Phase
   NaFlexVit.forward_intermediates() → image_features
   → HydraPool.forward() → logits (per-tag confidence)
   │
4. Postprocessing Phase
   sigmoid(logits) → probabilities
   → top-k selection → category lookup → auto meta-tags
   → JSON response
```

### Key Data Structures

| Structure | Type | Description |
|----------|------|-------------|
| `patches` | Tensor (seq_len, 768) | Image patches as pixel values |
| `patch_coords` | Tensor (seq_len, 2) | Spatial coordinates (y, x) |
| `patch_valid` | Tensor (seq_len,) | Valid patch mask |
| `logits` | Tensor (num_tags,) | Raw model outputs |
| `probs` | Tensor (num_tags,) | Sigmoid activations |
| `tags_with_probs` | List[dict] | Sorted tag predictions |

### Image Processing Pipeline

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Input     │────▶│  Resize     │────▶│  Patchify  │
│  Image     │     │  (max seq)  │     │  (16x16)  │
└──────────────┘     └──────────────┘     └──────────────┘
                                                 │
                              ┌───────────────────┼───────────────────┐
                              ▼                   ▼                   ▼
                       ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                       │   patches   │  │patch_coords │  │patch_valid │
                       │ uint8 (768) │  │ int16 (2)   │  │  bool      │
                       └──────────────┘  └──────────────┘  └──────────────┘
```

## Configuration Flow

```
Environment Variables (app.py)
    │
    ├── MODEL_PATH → load_model() → NaFlexVit + HydraPool
    ├── TAGS_PATH → load_metadata() → tag categories, implications
    ├── DEVICE → CUDA/CPU selection
    ├── MAX_SEQ_LEN → image resize constraint
    ├── SAVE_UPLOADS → file persistence
    └── USE_PROXY → ProxyFix middleware
```

## Security Architecture

### Request Pipeline

```
1. Client Request
   │
2. ProxyFix (if USE_PROXY=true)
   │ - x_for, x_proto, x_host, x_prefix
   │
3. Flask Router
   │ - /, /predict, /health, /static/*
   │
4. Rate Limiter
   │ - 500/hour, 20/minute for /predict
   │
5. Security Headers
   │ - HSTS, X-Frame-Options, CSP, etc.
   │
6. Response
```

### Security Headers Set

| Header | Value |
|--------|-------|
| Strict-Transport-Security | max-age=31536000; includeSubDomains |
| X-Frame-Options | DENY |
| X-Content-Type-Options | nosniff |
| Referrer-Policy | strict-origin-when-cross-origin |
| Permissions-Policy | geolocation=(), microphone=(), camera=() |
| Content-Security-Policy | (see app.py line 147 for full CSP string) |

## Extension System

The model supports extension files for adding new classification tags. Extensions are loaded via the `discover_extensions()` function in `model.py`.

### Extension Format

- Format: SAFETENSORS with metadata
- Architecture: Must match base model (`naflexvit_so400m_patch16_siglip+rr_hydra`)
- Metadata required:
  - `modelspec.implementation`: `redrocket.extension.label.v1`
  - `classifier.label`: Tag name
  - `classifier.label.category`: Category (general, artist, etc.)
  - `classifier.label.implies`: Space-separated implied tags

### Extension Loading

```
extensions directory
    │
    ├── extension1.safetensors  → load_extension()
    └── extension2.safetensors  → HydraPool.load_extensions()
```

## Logging Architecture

The application uses structured logging with emoji prefixes for easy parsing:

| Prefix | Context |
|--------|---------|
| 👤 | User request (method, path, IP, device, duration) |
| 📤 | Prediction request |
| 📥 | File upload |
| ✅ | Successful operation |
| ⚠️ | Warning |
| ❌ | Error |
| 🔄 | Health check |
| 📄 | Debug request |

### Log Format

```
2024-01-01 12:00:00 [INFO] 👤 POST / 192.168.1.1 📱 iOS/Safari 200 🟢 150.5ms
2024-01-01 12:00:01 [INFO] 📥 IP=192.168.1.1: uploading file 'image.png'
2024-01-01 12:00:02 [INFO] ✅ IP=192.168.1.1: file 'image.png' processed, top=200 tags (auto=5)
```

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Production                          │
│  ┌─────────────────────────────────────────���─���─┐   │
│  │  Traefik (Reverse Proxy)                   │   │
│  │  - TLS termination                     │   │
│  │  - Route to container                │   │
│  └─────────────────────────────────────┘   │
│                      │                          │
│  ┌─────────────────────────────────────────────┐   │
│  │  Docker (e621tagger:latest)            │   │
│  │  - Gunicorn (1 worker)              │   │
│  │  - PyTorch + CUDA                   │   │
│  │  - Model in memory                  │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Memory Requirements

| Component | GPU | RAM | Notes |
|-----------|-----|-----|-------|
| Model (JTP-3 Hydra) | ~2GB | ~2GB | Single model load (bfloat16) |
| Image patches (batch) | ~50MB | ~50MB | Per-request processing |
| Flask/Gunicorn | - | ~100MB | Application overhead |
| **Total (single worker, CUDA)** | ~2.1GB | ~2.2GB | |

### Multi-Worker Memory

When using multiple Gunicorn workers, each worker loads its own model copy:

| Workers | GPU Memory | RAM (app) | Recommended GPU |
|---------|------------|-----------|-----------------|
| 1 | ~2GB | ~2.2GB | 4GB VRAM |
| 2 | ~4GB | ~4.4GB | 6GB VRAM |
| 4 | ~8GB | ~8.8GB | 12GB VRAM |

> **Note:** Each additional Gunicorn worker adds ~2GB of model memory. For production with redundancy, use 2 workers with a GPU that has at least 6GB VRAM.

## File Structure

```
e621tagger/
├── app.py                    # Flask application
├── model.py                  # Model loading, image processing
├── inference.py              # CLI batch processing
├── siglip2.py               # NaFlex ViT backbone
├── hydra_pool.py            # Hydra attention pooling
├── image.py                # Image processing
├── loader.py               # Multi-process loader
├── templates/
│   ├── index.html          # Main UI template
│   └── service-worker.js   # PWA service worker (Jinja2 template rendered at runtime)
├── static/
│   ├── css/style.css       # Frontend styles
│   ├── js/script.js       # Frontend logic
│   ├── js/sw-init.js     # SW registration
│   ├── manifest.json    # PWA manifest
│   └── icons/            # App icons
├── .github/
│   ├── workflows/
│   │   └── docker-publish.yml
│   ├── compose.yml
│   └── compose-test.yml
└── Dockerfile
```

> **Note:** The service worker (`templates/service-worker.js`) is a Jinja2 template that gets rendered at runtime with the `APP_VERSION` variable. It is served via the `/service-worker.js` route, not as a static file.