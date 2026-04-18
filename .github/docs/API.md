# e621tagger API Documentation

This document provides comprehensive API documentation for agent integration. It covers all Flask endpoints, request/response contracts, error handling, and usage examples.

## Base URL

```
Production: https://tagger.fenrir784.ru
Local:      http://localhost:5000
```

## Endpoints Overview

| Method | Path | Description | Rate Limit |
|--------|------|-------------|------------|
| GET | `/` | Main UI page | - |
| POST | `/predict` | Submit image for tagging | 20/min, 500/hr |
| GET | `/health` | Health check | - |
| GET | `/service-worker.js` | PWA service worker | - |
| GET | `/static/<path>` | Static assets | - |
| GET | `/favicon.ico` | Favicon | - |
| GET | `/robots.txt` | Robots.txt | - |
| GET | `/sitemap.xml` | Sitemap | - |

---

## GET / - Main UI Page

Returns the main HTML interface for image tagging.

### Request

```
GET / HTTP/1.1
Host: tagger.fenrir784.ru
```

### Response

```html
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Content-Security-Policy: ...

<!DOCTYPE html>
<html lang="en">
<head>
    <title>e621tagger</title>
    ...
</head>
<body>
    <div class="container">
        <header>...</header>
        <main>
            <div id="dropZone">...</div>
            <div class="results">...</div>
        </main>
    </div>
</body>
</html>
```

### Security Headers

All responses include these headers:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://e621.net; object-src 'none'; base-uri 'self';
```

---

## POST /predict - Image Classification

Submit an image for AI-powered tag generation.

### Rate Limits

| Limit | Window | Scope |
|-------|--------|-------|
| 20 requests | per minute | `/predict` endpoint only |
| 500 requests | per hour | All endpoints (global default) |

Exceeding limits returns HTTP 429.

### Request

```
POST /predict HTTP/1.1
Host: tagger.fenrir784.ru
Content-Type: multipart/form-data
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `image` | file | Yes | Image file (JPEG, PNG, GIF, WebP, BMP, TIFF) |
| `top_k` | integer | No | Number of tags to return (default: 200) |

### Allowed Values

- **top_k**: 50, 75, 100, 150, 200, 300
- **image formats**: .jpg, .jpeg, .png, .gif, .webp, .bmp, .tiff
- **max file size**: 20MB

### Request Example

```bash
# Using curl
curl -X POST https://tagger.fenrir784.ru/predict \
  -F "image=@artwork.png" \
  -F "top_k=200"

# Python example
import requests

with open("artwork.png", "rb") as f:
    response = requests.post(
        "https://tagger.fenrir784.ru/predict",
        files={"image": f},
        data={"top_k": "200"}
    )
```

### Response (Success)

```json
HTTP/1.1 200 OK
Content-Type: application/json

{
  "success": true,
  "tags": [
    {
      "tag": "female",
      "prob": 0.95,
      "category": "General"
    },
    {
      "tag": "anthro",
      "prob": 0.89,
      "category": "Species"
    },
    {
      "tag": "furry",
      "prob": 0.87,
      "category": "General"
    },
    {
      "tag": "safe",
      "prob": 0.92,
      "category": "Meta"
    },
    ...
  ],
  "auto_meta": [
    "hi_res",
    "16:9"
  ]
}
```

> **Note:** Rating tags (`safe`, `questionable`, `explicit`) appear in the `tags` array as model predictions, not in `auto_meta`. The `auto_meta` field contains automatically-detected technical tags like resolution and aspect ratio.

### Tag Object Structure

| Field | Type | Description |
|-------|------|-------------|
| `tag` | string | Tag name |
| `prob` | float | Confidence probability (0.0 to 1.0) |
| `category` | string | e621 category name |

### Categories

| ID | Name |
|----|------|
| 0 | General |
| 1 | Artist |
| 3 | Copyright |
| 4 | Character |
| 5 | Species |
| 7 | Meta |
| 8 | Lore |

### Auto-Generated Meta Tags

These tags are automatically added based on image properties:

| Tag | Condition |
|-----|----------|
| `animated` | GIF with multiple frames |
| `thumbnail` | Width ≤ 250px and height ≤ 250px |
| `low_res` | Width ≤ 500px and height ≤ 500px |
| `hi_res` | Width ≥ 1600px OR height ≥ 1200px |
| `absurd_res` | Width ≥ 3200px OR height ≥ 2400px |
| `superabsurd_res` | Width ≥ 10000px AND height ≥ 10000px |
| `4k` | 3840x2160, 2160x3840, 4096x2160, or 2160x4096 |
| `long_image` | Aspect ratio ≥ 4:1 or ≤ 1:4 |
| `tall_image` | Aspect ratio ≤ 1:4 (subset of long_image) |
| `widescreen` | Aspect ratio 16:9 or ~16:10 |
| `1:1`, `2:1`, `16:9`, etc. | Standard aspect ratios |

### Response (Error)

```json
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": "No image provided"
}
```

```json
HTTP/1.1 413 Request Entity Too Large
Content-Type: application/json

{
  "error": "File too large. Maximum size is 20MB."
}
```

### Error Codes

| Status | Error | Description |
|--------|-------|-------------|
| 400 | `No image provided` | Missing `image` field |
| 400 | `Empty filename` | Empty filename parameter |
| 400 | `File type not allowed` | Unsupported file extension |
| 400 | `Invalid or corrupted image file` | Image verification failed |
| 413 | `File too large` | Exceeds 20MB limit |
| 429 | Rate limit exceeded | Too many requests |
| 500 | `Internal server error` | Processing failed |

---

## GET /health - Health Check

Check if the service is operational.

### Request

```
GET /health HTTP/1.1
Host: tagger.fenrir784.ru
```

### Response (Healthy)

```json
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "healthy",
  "model": "loaded",
  "tags_count": 7500,
  "version": "v123"
}
```

### Response (Unhealthy)

```json
HTTP/1.1 503 Service Unavailable
Content-Type: application/json

{
  "status": "unhealthy",
  "reason": "model not loaded"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `healthy` or `unhealthy` |
| `model` | string | `loaded` if healthy |
| `tags_count` | integer | Number of tags in model |
| `version` | string | Application version |
| `reason` | string | Error reason if unhealthy |

---

## GET /static/<path> - Static Assets

Serve static files (CSS, JS, icons).

### Request

```
GET /static/css/style.css HTTP/1.1
Host: tagger.fenrir784.ru
```

### Response

```
HTTP/1.1 200 OK
Content-Type: text/css
Cache-Control: public, max-age=86400
```

### Caching

Static assets are cached for 24 hours:

```
Cache-Control: public, max-age=86400
```

---

## GET /service-worker.js - PWA Service Worker

Serve the service worker script for PWA functionality.

### Request

```
GET /service-worker.js HTTP/1.1
Host: tagger.fenrir784.ru
```

### Response

```
HTTP/1.1 200 OK
Content-Type: application/javascript
Cache-Control: no-cache, no-store, must-revalidate
Pragma: no-cache
Expires: 0
```

### Note

Service worker is cached by the browser's SW cache, not HTTP cache. Cache headers prevent HTTP caching but allow SW caching.

---

## GET /favicon.ico - Favicon

### Response

```
HTTP/1.1 200 OK
Content-Type: image/vnd.microsoft.icon
Cache-Control: public, max-age=86400
```

---

## GET /robots.txt - Robots.txt

### Request

```
GET /robots.txt HTTP/1.1
Host: tagger.fenrir784.ru
```

### Response

```
HTTP/1.1 200 OK
Content-Type: text/plain

User-agent: *
Disallow: /static/
Disallow: /predict
Disallow: /health
Disallow: /service-worker.js

Sitemap: https://www.tagger.fenrir784.ru/sitemap.xml
```

---

## GET /sitemap.xml - Sitemap

### Request

```
GET /sitemap.xml HTTP/1.1
Host: tagger.fenrir784.ru
```

### Response

```xml
HTTP/1.1 200 OK
Content-Type: application/xml

<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.tagger.fenrir784.ru/</loc>
    <lastmod>2024-01-01</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
```

---

## Python Integration Example

```python
import requests
from PIL import Image
import io

class E621Tagger:
    def __init__(self, base_url="https://tagger.fenrir784.ru"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def check_health(self) -> dict:
        """Check service health."""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def tag_image(
        self,
        image_path: str = None,
        image_bytes: bytes = None,
        top_k: int = 200
    ) -> dict:
        """
        Tag an image.
        
        Args:
            image_path: Path to image file
            image_bytes: Raw image bytes
            top_k: Number of tags to return (50-300)
        
        Returns:
            dict with 'success', 'tags', 'auto_meta'
        """
        if image_path:
            with open(image_path, "rb") as f:
                files = {"image": f}
        elif image_bytes:
            files = {"image": io.BytesIO(image_bytes)}
        else:
            raise ValueError("Must provide image_path or image_bytes")
        
        data = {"top_k": str(top_k)}
        response = self.session.post(
            f"{self.base_url}/predict",
            files=files,
            data=data
        )
        response.raise_for_status()
        return response.json()
    
    def tag_image_pil(self, image: Image.Image, top_k: int = 200) -> dict:
        """Tag a PIL Image."""
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        
        files = {"image": ("image.png", buf, "image/png")}
        response = self.session.post(
            f"{self.base_url}/predict",
            files=files,
            data={"top_k": str(top_k)}
        )
        response.raise_for_status()
        return response.json()

# Usage
tagger = E621Tagger()

# Check health
health = tagger.check_health()
print(f"Status: {health['status']}")
print(f"Tags: {health['tags_count']}")

# Tag an image
result = tagger.tag_image("artwork.png")
print(f"Success: {result['success']}")
print(f"Tags returned: {len(result['tags'])}")

# Print top tags
for tag in result["tags"][:10]:
    print(f"  {tag['tag']}: {tag['prob']:.2%} ({tag['category']})")
```

---

## JavaScript Integration Example

```javascript
class E621Tagger {
    constructor(baseUrl = 'https://tagger.fenrir784.ru') {
        this.baseUrl = baseUrl;
    }
    
    async checkHealth() {
        const response = await fetch(`${this.baseUrl}/health`);
        return response.json();
    }
    
    async tagImage(file, topK = 200) {
        const formData = new FormData();
        formData.append('image', file);
        formData.append('top_k', topK.toString());
        
        const response = await fetch(`${this.baseUrl}/predict`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Request failed');
        }
        
        return response.json();
    }
}

// Usage
const tagger = new E621Tagger();

const fileInput = document.getElementById('fileInput');
fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    const result = await tagger.tagImage(file);
    
    console.log('Success:', result.success);
    console.log('Tags:', result.tags);
    console.log('Auto Meta:', result.auto_meta);
});
```

---

## Rate Limiting

The application uses `flask-limiter` for rate limiting.

### Limits

| Endpoint | Limit |
|----------|-------|
| `/predict` | 20 per minute, 500 per hour |
| Default | Inherited |

### Rate Limit Headers

When rate limited, responses include:

```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 60

{
  "error": "Rate limit exceeded"
}
```

### Implementation

Located in `app.py`:

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

---

## Content Security Policy

The application sets a strict CSP:

```
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://e621.net; object-src 'none'; base-uri 'self';
```

### Directives

| Directive | Value | Purpose |
|----------|-------|---------|
| default-src | 'self' | Default: same origin |
| img-src | 'self' data: blob: | Images: same origin, data URLs, blobs |
| script-src | 'self' | Scripts: same origin only |
| style-src | 'self' 'unsafe-inline' | Styles: same origin + inline |
| connect-src | 'self' https://e621.net | Fetch: same origin + e621 |
| object-src | 'none' | No plugins/objects |
| base-uri | 'self' | Base URL: same origin |