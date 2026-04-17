# app.py Reference Documentation

This document provides a comprehensive reference for all methods, variables, and configurations in `app.py` (485 lines). It is designed for agent systems to understand and interact with the e621tagger Flask application.

---

## File Overview

| Attribute | Value |
|-----------|-------|
| Location | `app.py` |
| Lines | 485 |
| Framework | Flask |
| Purpose | Web application for e621 image tagging |
| Dependencies | flask, flask-limiter, torch, PIL, ua-parser |

### File Structure Flow

```
app.py
├── 1. Imports (lines 1-18)
│   └── Standard library + Flask + ML dependencies
│
├── 2. Global Constants (lines 20-65)
│   ├── TAG_CATEGORIES - Tag ID to name mapping
│   ├── APP_CONFIG - Version, logging, app setup
│   ├── MODEL_CONFIG - Model paths and device settings
│   ├── FILE_LIMITS - Upload and file type limits
│   └── Flask + Limiter initialization
│
├── 3. Helper Functions (lines 67-134)
│   └── Logging and user agent utilities
│
├── 4. Request Hooks (lines 136-189)
│   ├── @before_request - Start timing
│   └── @after_request - Security headers + logging
│
├── 5. Startup (lines 191-215)
│   ├── Directory creation
│   ├── Model loading
│   └── Metadata loading
│
├── 6. Validation Functions (lines 217-230)
│   ├── is_valid_image() - Verify image
│   └── is_allowed_file() - Check extension/MIME
│
├── 7. Processing Functions (lines 231-305)
│   ├── detect_meta_tags_for_image_path() - Auto tags
│   └── save_upload() - File persistence
│
├── 8. Flask Routes (lines 312-482)
│   └── 10 endpoints (+ error handler)
│
└── 9. Main Entry (lines 484-485)
    └── Production run
```

---

## 1. Global Constants

### Tag Categories

```python
TAG_CATEGORIES = {
    0: "General",
    1: "Artist",
    3: "Copyright",
    4: "Character",
    5: "Species",
    7: "Meta",
    8: "Lore",
}
```
| Usage | Map tag category IDs to e621 category names |
| ---- | ------------------------------------ |

### Application Configuration

```python
APP_VERSION = os.getenv('APP_VERSION', 'test')
LOG_LEVEL = logging.DEBUG if APP_VERSION.startswith('test-') else logging.INFO
```
| Variable | Default | Description |
|----------|---------|-------------|
| `APP_VERSION` | `test` | Version string (set by Docker build) |
| `LOG_LEVEL` | DEBUG/test, INFO/prod | Logging level based on version |

### Flask Application

```python
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
```
| Config | Value | Description |
|--------|-------|-------------|
| `MAX_CONTENT_LENGTH` | 20MB | Maximum upload file size |

### Rate Limiter

```python
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["500 per hour"],
    storage_uri="memory://",
)
```
| Limit | Scope |
|-------|-------|
| 500/hour | All endpoints |
| 20/minute | `/predict` (decorated) |

### Model Configuration

```python
MODEL_PATH = os.getenv('MODEL_PATH', 'models/jtp-3-hydra.safetensors')
TAGS_PATH = os.getenv('TAGS_PATH', 'data/jtp-3-hydra-tags.csv')
DEVICE = os.getenv('DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')
MAX_SEQ_LEN = int(os.getenv('MAX_SEQ_LEN', '1024'))
PATCH_SIZE = 16
```
| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PATH` | `models/jtp-3-hydra.safetensors` | Model file location |
| `TAGS_PATH` | `data/jtp-3-hydra-tags.csv` | Tag metadata CSV |
| `DEVICE` | cuda/cpu | PyTorch device |
| `MAX_SEQ_LEN` | 1024 | Max patches for input |
| `PATCH_SIZE` | 16 | Patch size (pixels) |

### Prediction Settings

```python
DEFAULT_TOP_K = 200
ALLOWED_TOP_K = {50, 75, 100, 150, 200, 300}
```
| Variable | Value | Description |
|----------|-------|-------------|
| `DEFAULT_TOP_K` | 200 | Default tag count |
| `ALLOWED_TOP_K` | {50,75,100,150,200,300} | Valid top_k values |

### File Handling

```python
SAVE_UPLOADS = os.getenv('SAVE_UPLOADS', 'false').lower() == 'true'
UPLOAD_DIR = os.getenv('UPLOAD_DIR', '/app/uploads')
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff'}
```
| Variable | Default | Description |
|----------|---------|-------------|
| `SAVE_UPLOADS` | false | Save uploads to disk |
| `UPLOAD_DIR` | `/app/uploads` | Upload save directory |
| `ALLOWED_EXTENSIONS` | 7 formats | Valid file extensions |
| `ALLOWED_MIME_TYPES` | 7 MIME types | Valid MIME types |

---

## 2. Helper Functions

### secure_log(s: str) -> str

| Location | app.py:67-72 |
|----------|-------------|
| Input | `s: str` - Raw string |
| Output | `str` - Sanitized string |
| Purpose | Remove control characters and newlines from log strings |

```python
def secure_log(s: str) -> str:
    if not s:
        return ""
    s = s.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    s = re.sub(r'[\x00-\x1f\x7f]', '', s)
    return s.strip()
```

### status_emoji(status_code: int) -> str

| Location | app.py:74-80 |
|----------|---------------|
| Input | `status_code: int` - HTTP status code |
| Output | `str` - Emoji (🟢/🟡/🔴) |
| Purpose | Get status emoji for logging |

| Status Range | Emoji |
|-------------|-------|
| 200-299 | 🟢 |
| 300-399 | 🟡 |
| 400+ | 🔴 |

### get_country_flag(accept_lang: str) -> str

| Location | app.py:82-90 |
|----------|----------------|
| Input | `accept_lang: str` - Accept-Language header |
| Output | `str` - Country flag emoji |
| Purpose | Extract country code from Accept-Language header |

### parse_user_agent(ua_str: str) -> tuple[str, str]

| Location | app.py:92-134 |
|----------|--------------------|
| Input | `ua_str: str` - User-Agent string |
| Output | `tuple[str, str]` - (device_type, ua_string) |
| Purpose | Parse User-Agent string into device type and short UA |

| Device Type | Detection |
|-----------|-----------|
| bot | spider, bot, crawler |
| mobile | smartphone, or "mobile" in UA |
| tablet | tablet |
| desktop | default |

---

## 3. Request Hooks

### @app.before_request

| Location | app.py:136-138 |
|----------|----------------|
| Purpose | Start request timing for duration tracking |
| Sets | `g.start_time` - Request start timestamp |

### @app.after_request

| Location | app.py:140-189 |
|----------|------------------|
| Purpose | Add security headers and request logging |
| Headers Added | HSTS, X-Frame-Options, CSP, etc. |

**Security Headers Added:**

| Header | Value |
|--------|-------|
| Strict-Transport-Security | max-age=31536000; includeSubDomains |
| X-Frame-Options | DENY |
| X-Content-Type-Options | nosniff |
| Referrer-Policy | strict-origin-when-cross-origin |
| Permissions-Policy | geolocation=(), microphone=(), camera=() |
| Content-Security-Policy | default-src 'self'; img-src 'self' data: blob:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://e621.net; object-src 'none'; base-uri 'self'; |

---

## 4. Image Validation Functions

### is_valid_image(file) -> bool

| Location | app.py:217-225 |
|----------|-----------------|
| Input | `file` - File-like object |
| Output | `bool` - True if valid image |
| Purpose | Verify file is a valid image |

```python
def is_valid_image(file):
    try:
        file.seek(0)
        img = Image.open(file)
        img.verify()
        file.seek(0)
        return True
    except Exception:
        return False
```

### is_allowed_file(filename: str, content_type: str) -> bool

| Location | app.py:227-229 |
|----------|-------------------|
| Input | `filename: str`, `content_type: str` |
| Output | `bool` - True if allowed |
| Purpose | Check file extension and MIME type |

---

## 5. Processing Functions

### detect_meta_tags_for_image_path(image_path: str) -> set[str]

| Location | app.py:231-287 |
|--------------------|----------------------|
| Input | `image_path: str` - Path to image file |
| Output | `set[str]` - Auto-detected meta tags |
| Purpose | Generate meta tags from image properties |

| Tag | Condition |
|-----|----------|
| animated | GIF with n_frames > 1 |
| thumbnail | w ≤ 250 and h ≤ 250 |
| low_res | w ≤ 500 and h ≤ 500 |
| hi_res | w ≥ 1600 or h ≥ 1200 |
| absurd_res | w ≥ 3200 or h ≥ 2400 |
| 4k | Exact 3840x2160/4096x2160 variants |
| superabsurd_res | w ≥ 10000 and h ≥ 10000 |
| long_image | ratio ≥ 4:1 or ≤ 1:4 |
| tall_image | ratio ≤ 1:4 |
| 1:1, 2:1, 16:9, etc. | Exact aspect ratios |
| widescreen | 16:9 or ~16:10 |

### save_upload(file, original_filename: str) -> str | None

| Location | app.py:289-305 |
|----------|--------------------|
| Input | `file`, `original_filename: str` |
| Output | `str` - Save path, or None on failure |
| Purpose | Save uploaded file to disk |
| Requirement | `SAVE_UPLOADS=true` |

---

## 6. Flask Routes

### index() -> str

| Location | app.py:312-314 |
|----------|----------------|
| Route | `GET /` |
| Output | HTML - Rendered `index.html` |
| Purpose | Main UI page |

### favicon() -> Response

| Location | app.py:316-320 |
|----------|----------------|
| Route | `GET /favicon.ico` |
| Output | ICO file with 24h caching |
| Purpose | Serve favicon |

### static_files(filename: str) -> Response

| Location | app.py:322-326 |
|-------------------|----------------|
| Route | `GET /static/<path>` |
| Input | `filename: str` - File path |
| Output | Static file with 24h caching |
| Purpose | Serve CSS, JS, icons |

### service_worker() -> Response

| Location | app.py:328-335 |
|----------|----------------|
| Route | `GET /service-worker.js` |
| Output | JS with no-cache headers |
| Purpose | PWA service worker |

### health() -> tuple

| Location | app.py:337-353 |
|----------|---------------|
| Route | `GET /health` |
| Output | JSON - Health status |
| Purpose | Health check endpoint |

**Healthy Response:**
```json
{
  "status": "healthy",
  "model": "loaded",
  "tags_count": 7500,
  "version": "v123"
}
```

**Unhealthy Response (503):**
```json
{
  "status": "unhealthy",
  "reason": "model not loaded"
}
```

### predict() -> tuple

| Location | app.py:355-456 |
|----------|----------------|
| Route | `POST /predict` |
| Rate Limit | 20/minute |
| Input | `image` file (multipart/form-data), optional `top_k` |
| Output | JSON - Tag predictions |

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| image | file | Yes | Image file |
| top_k | int | No | Number of tags (50-300, default 200) |

**Success Response:**
```json
{
  "success": true,
  "tags": [
    {"tag": "female", "prob": 0.95, "category": "General"},
    {"tag": "anthro", "prob": 0.89, "category": "Species"}
  ],
  "auto_meta": ["hi_res", "16:9"]
}
```

**Error Responses:**

| Status | Error Message |
|--------|----------------|
| 400 | "No image provided" |
| 400 | "Empty filename" |
| 400 | "File type not allowed" |
| 400 | "Invalid or corrupted image file" |
| 413 | "File too large. Maximum size is 20MB." |
| 500 | "Internal server error" |

### robots() -> Response

| Location | app.py:458-468 |
|----------|----------------|
| Route | `GET /robots.txt` |
| Output | Robots.txt content |
| Purpose | Search engine instructions |

**Content:**
```
User-agent: *
Disallow: /static/
Disallow: /predict
Disallow: /health
Disallow: /service-worker.js

Sitemap: https://www.tagger.fenrir784.ru/sitemap.xml
```

### sitemap() -> Response

| Location | app.py:470-482 |
|----------|----------------|
| Route | `GET /sitemap.xml` |
| Output | XML sitemap |
| Purpose | SEO sitemap |

### handle_file_too_large(e) -> tuple

| Location | app.py:307-310 |
|----------|-------------------|
| Handler | 413 errors |
| Purpose | Handle file too large |

---

## 7. Runtime Initialization

These run at module load time (lines 191-215):

```python
# 1. Create upload directory
if SAVE_UPLOADS:
    os.makedirs(UPLOAD_DIR, exist_ok=True)

# 2. Load ML model
model, tag_list, ext_info = load_model(MODEL_PATH, device=DEVICE)

# 3. Convert dtype based on device
if DEVICE == 'cpu':
    model = model.float()  # float32 for CPU
else:
    model = model.to(dtype=torch.bfloat16)  # bfloat16 for GPU

# 4. Set model to inference mode
model.requires_grad_(False)
model.eval()

# 5. Load tag metadata
metadata = load_metadata(TAGS_PATH)
```

### Global Runtime Objects

| Object | Type | Description |
|--------|------|-------------|
| `model` | NaFlexVit | Loaded ML model |
| `tag_list` | list[str] | All tag names (~7500) |
| `ext_info` | dict | Extension info |
| `metadata` | dict | Tag categories and implications |

---

## 8. Entry Point

```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
```

| Setting | Value | Description |
|--------|-------|-------------|
| Host | 0.0.0.0 | Accept all interfaces |
| Port | 5000 | Default port |
| debug | False | Production mode |

---

## Quick Reference for Agents

### Calling the API

```bash
# Health check
curl http://localhost:5000/health

# Tag an image
curl -X POST -F "image=@file.png" \
     -F "top_k=200" \
     http://localhost:5000/predict
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| APP_VERSION | No | Version string |
| MODEL_PATH | No | Model file path |
| DEVICE | No | cuda or cpu |
| MAX_SEQ_LEN | No | Max patches |

### Error Handling

The app returns different HTTP status codes:
- 200: Success
- 400: Bad request (missing file, invalid type)
- 413: File too large
- 429: Rate limit exceeded
- 500: Internal error

### Logging

All logs include timestamp, level, and emoji prefix:
- 🚀 - Startup/version
- ⚙️ - Loading
- ✅ - Success
- ⚠️ - Warning
- ❌ - Error
- 📥 - Upload
- 📤 - Prediction request
- 👤 - Page view