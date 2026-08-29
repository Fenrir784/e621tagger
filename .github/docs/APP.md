# app.py Reference Documentation

This document provides a comprehensive reference for all methods, variables, and configurations in `app.py` (540 lines). It is designed for agent systems to understand and interact with the e621tagger Flask application.

---

## File Overview

| Attribute | Value |
|-----------|-------|
| Location | `app.py` |
| Lines | 540 |
| Framework | Flask |
| Purpose | Web application for e621 image tagging |
| Dependencies | flask, flask-limiter, torch, PIL, ua-parser |

### File Structure Flow

```
app.py
├── 1. Imports (lines 1-18)
│   └── Standard library + Flask + ML dependencies
│
├── 2. Global Constants (lines 20-83)
│   ├── TAG_CATEGORIES - Tag ID to name mapping
│   ├── SUBCATEGORY_DISPLAY_NAMES - Subcategory code to display name
│   ├── APP_CONFIG - Version, logging, app setup
│   ├── MODEL_CONFIG - Model paths and device settings
│   ├── FILE_LIMITS - Upload and file type limits
│   └── Flask + Limiter initialization
│
├── 3. Helper Functions (lines 84-163)
│   └── Logging and user agent utilities
│
├── 4. Request Hooks (lines 165-227)
│   ├── @before_request - Start timing
│   └── @after_request - Security headers + logging
│
├── 5. Startup (lines 229-251)
│   ├── Directory creation
│   ├── Model loading
│   └── Metadata loading
│
├── 6. Validation Functions (lines 253-265)
│   ├── is_valid_image() - Verify image
│   └── is_allowed_file() - Check extension/MIME
│
├── 7. Processing Functions (lines 267-341)
│   ├── detect_meta_tags_for_image_path() - Auto tags
│   └── save_upload() - File persistence
│
├── 8. Flask Routes (lines 343-537)
│   └── 10 endpoints (+ error handler)
│
└── 9. Main Entry (lines 539-540)
    └── Production run
```

---

## 1. Global Constants

### Tag Categories

```python
TAG_CATEGORIES = {
    "general": "General",
    "artist": "Artist",
    "contributor": "Contributor",
    "copyright": "Copyright",
    "character": "Character",
    "species": "Species",
    "invalid": "Invalid",
    "meta": "Meta",
    "lore": "Lore",
}
```
| Usage | Map tag category string keys to e621 category display names |
| ---- | ------------------------------------ |

> **Note:** The Label class in `hydra/label.py` uses integer category IDs (0-8, 100-111). The TAG_CATEGORIES dict here maps string keys for the 9 base categories. Subcategories (100-111) are handled via SUBCATEGORY_DISPLAY_NAMES.

### Subcategory Display Names

```python
SUBCATEGORY_DISPLAY_NAMES = {
    "accessory": "Accessories, Items, Clothing",
    "action": "Actions, Positions, State",
    "color": "Body Color",
    "body_feature": "Body Features",
    "effect": "Effects, Fluids",
    "fetish": "Fetishes, Specifics, Interactions",
    "demographic": "Genders, Demographics",
    "setting": "Locations, Backgrounds, Setting",
    "pose": "Poses, Scenarios, Situations",
    "style": "Style, Perspective",
    "text": "Text, Symbols, UI, Vocalization",
    "other": "Other",
}
```
| Usage | Map internal subcategory codes to display names for the API response and UI |
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
MODEL_PATH = os.getenv('MODEL_PATH', 'models/hydra-3.5.safetensors')
DEVICE = os.getenv('DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')
MAX_SEQ_LEN = int(os.getenv('MAX_SEQ_LEN', '1024'))
PATCH_SIZE = 16
```
| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PATH` | `models/hydra-3.5.safetensors` | Model file location |
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

### secure_log(s: str | None) -> str

| Location | app.py:84-89 |
|----------|-------------|
| Input | `s: str | None` - Raw string |
| Output | `str` - Sanitized string |
| Purpose | Remove control characters and newlines from log strings |

```python
def secure_log(s: str | None) -> str:
    if not s:
        return ""
    s = s.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    s = re.sub(r'[\x00-\x1f\x7f\u0080-\u009f\u200b\u202e\u2066-\u2069]', '', s)
    return s.strip()
```

### status_emoji(status_code) -> str

| Location | app.py:91-97 |
|----------|---------------|
| Input | `status_code: int` - HTTP status code |
| Output | `str` - Emoji (🟢/🟡/🔴) |
| Purpose | Get status emoji for logging |

| Status Range | Emoji |
|-------------|-------|
| 200-299 | 🟢 |
| 300-399 | 🟡 |
| 400+ | 🔴 |

### get_country_flag(accept_lang) -> str

| Location | app.py:99-107 |
|----------|----------------|
| Input | `accept_lang: str` - Accept-Language header |
| Output | `str` - Country flag emoji |
| Purpose | Extract country code from Accept-Language header |

### get_ip_identifier(ip: str | None) -> str

| Location | app.py:109-119 |
|----------|----------------|
| Input | `ip: str` - IP address string |
| Output | `str` - Colored IP identifier (e.g., "🟪 192.168.1.1") |
| Purpose | Generate consistent color + IP string for logging |

The function uses a simple hash of the IP's octets to generate a consistent color. Same IP always maps to same color.

| Hash Index | Emoji | Color |
|------------|-------|-------|
| 0 | ⬛️ | Black |
| 1 | 🟫 | Brown |
| 2 | 🟪 | Purple |
| 3 | 🟦 | Blue |
| 4 | 🟩 | Green |
| 5 | ⬜ | White |
| 6 | 🟨 | Yellow |
| 7 | 🟧 | Orange |
| 8 | 🟥 | Red |

### parse_user_agent(ua_str: str) -> tuple[str, str]

| Location | app.py:121-163 |
|----------|--------------------|
| Input | `ua_str: str` - User-Agent string |
| Output | `tuple[str, str]` - (device_type, ua_string) |
| Purpose | Parse User-Agent string into device type and short UA |

| Device Type | Detection |
|-------------|-----------|
| bot | spider, bot, crawler |
| mobile | smartphone, or "mobile" in UA |
| tablet | tablet |
| desktop | default |

---

## 3. Request Hooks

### @app.before_request

| Location | app.py:165-167 |
|----------|----------------|
| Purpose | Start request timing for duration tracking |
| Sets | `g.start_time` - Request start timestamp |

### @app.after_request

| Location | app.py:169-227 |
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

| Location | app.py:253-261 |
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

| Location | app.py:263-265 |
|----------|-------------------|
| Input | `filename: str`, `content_type: str` |
| Output | `bool` - True if allowed |
| Purpose | Check file extension and MIME type |

---

## 5. Processing Functions

### detect_meta_tags_for_image_path(image_path: str) -> set[str]

| Location | app.py:267-323 |
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

**Note:** The current year tag (e.g., `2025`, `2026`) is added separately in the `/predict` endpoint after calling this function. It is not part of `detect_meta_tags_for_image_path()`.

### save_upload(file, original_filename) -> str | None

| Location | app.py:325-341 |
|----------|--------------------|
| Input | `file`, `original_filename: str` |
| Output | `str` - Save path, or None on failure |
| Purpose | Save uploaded file to disk |
| Requirement | `SAVE_UPLOADS=true` |

---

## 6. Flask Routes

### index() -> str

| Location | app.py:348-350 |
|----------|----------------|
| Route | `GET /` |
| Output | HTML - Rendered `index.html` |
| Purpose | Main UI page |

### favicon() -> Response

| Location | app.py:352-356 |
|----------|----------------|
| Route | `GET /favicon.ico` |
| Output | ICO file with 24h caching |
| Purpose | Serve favicon |

### static_files(filename: str) -> Response

| Location | app.py:358-362 |
|-------------------|----------------|
| Route | `GET /static/<path>` |
| Input | `filename: str` - File path |
| Output | Static file with 24h caching |
| Purpose | Serve CSS, JS, icons |

### service_worker() -> Response

| Location | app.py:364-371 |
|----------|----------------|
| Route | `GET /service-worker.js` |
| Output | JS with no-cache headers |
| Purpose | PWA service worker |

### health() -> tuple

| Location | app.py:373-389 |
|----------|---------------|
| Route | `GET /health` |
| Output | JSON - Health status |
| Purpose | Health check endpoint |

**Healthy Response:**
```json
{
  "status": "healthy",
  "model": "JTP-3 Hydra 3.5",
  "tags_count": 8888,
  "version": "APP_VERSION"
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

| Location | app.py:391-509 |
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
  "auto_meta": ["hi_res", "16:9", "2025"]
}
```

**Note:** The `auto_meta` array includes the current year (e.g., `2025`, `2026`) as a meta tag with 1.0 confidence. Frontend can filter this via the `addCurrentYearTag` setting (default: true).

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

| Location | app.py:514-523 |
|----------|----------------|
| Route | `GET /robots.txt` |
| Output | Robots.txt content |
| Purpose | Search engine instructions |

**Content:**
```
User-agent: *
Disallow: /predict
Disallow: /health
Disallow: /service-worker.js

Sitemap: https://www.tagger.fenrir784.app/sitemap.xml
```

### sitemap() -> Response

| Location | app.py:525-537 |
|----------|----------------|
| Route | `GET /sitemap.xml` |
| Output | XML sitemap |
| Purpose | SEO sitemap |

### handle_file_too_large(e) -> tuple

| Location | app.py:343-346 |
|----------|-------------------|
| Handler | 413 errors |
| Purpose | Handle file too large |

---

## 7. Runtime Initialization

These run at module load time (lines 229-251):

```python
# 1. Create upload directory
if SAVE_UPLOADS:
    os.makedirs(UPLOAD_DIR, exist_ok=True)

# 2. Load ML model — labels come from safetensors metadata
model = hydra_load_model(MODEL_PATH)

# 3. Convert dtype based on device
if DEVICE == 'cpu':
    model = model.float()  # float32 for CPU
else:
    model = model.to(dtype=torch.bfloat16, device=DEVICE)  # bfloat16 for GPU

# 4. Set model to inference mode
model.requires_grad_(False)
model.eval()
```

### Global Runtime Objects

| Object | Type | Description |
|--------|------|-------------|
| `model` | Hydra | Loaded ML model |
| `tag_list` | list[str] | All tag names (8,888 in Hydra 3.5) |
| `_SUBCATEGORY_MAP` | dict | 6,263 general → subcategory mappings (in `_subcat.py`) |

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