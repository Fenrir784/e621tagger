import os
import tempfile
import logging
import time
import re
import json
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template, send_from_directory, make_response, g
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import torch
from PIL import Image
from ua_parser import parse

from hydra.model import load_model as hydra_load_model
from hydra import image as hydra_image

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


APP_VERSION = os.getenv('APP_VERSION', 'test')
LOG_LEVEL = logging.DEBUG if APP_VERSION.startswith('test-') else logging.INFO
RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'false').lower() == 'true'

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("pyvips").setLevel(logging.WARNING)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
app.config['RATELIMIT_ENABLED'] = RATE_LIMIT_ENABLED

if os.getenv('USE_PROXY', 'false').lower() == 'true':
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["500 per hour"],
    storage_uri="memory://",
)

MODEL_PATH = os.getenv('MODEL_PATH', 'models/hydra-3.5.safetensors')
DEVICE = os.getenv('DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')
MAX_SEQ_LEN = int(os.getenv('MAX_SEQ_LEN', '1024'))
PATCH_SIZE = 16
DEFAULT_TOP_K = 200
ALLOWED_TOP_K = {50, 75, 100, 150, 200, 300}

SAVE_UPLOADS = os.getenv('SAVE_UPLOADS', 'false').lower() == 'true'
UPLOAD_DIR = os.getenv('UPLOAD_DIR', '/app/uploads')
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff'}

BAN_FILE = os.getenv('BAN_FILE', 'banned_ips.json')
STRIKE_WINDOW = 30 * 86400
BAN_3_STRIKES_DURATION = 3600
BAN_5_STRIKES_DURATION = 30 * 86400
BAN_3_STRIKES_THRESHOLD = 3
BAN_5_STRIKES_THRESHOLD = 5

def secure_log(s: str | None) -> str:
    if not s:
        return ""
    s = s.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    s = re.sub(r'[\x00-\x1f\x7f]', '', s)
    return s.strip()

def status_emoji(status_code):
    if 200 <= status_code < 300:
        return "🟢"
    elif 300 <= status_code < 400:
        return "🟡"
    else:
        return "🔴"

def get_country_flag(accept_lang):
    if not accept_lang:
        return ""
    first_lang = accept_lang.split(',')[0].strip()
    if '-' in first_lang:
        country_code = first_lang.split('-')[1].upper()
        if len(country_code) == 2 and country_code.isalpha():
            return chr(ord(country_code[0]) - ord('A') + 0x1F1E6) + chr(ord(country_code[1]) - ord('A') + 0x1F1E6)
    return ""

def get_ip_identifier(ip: str | None) -> str:
    colors = ['⬛️', '🟫', '🟪', '🟦', '🟩', '⬜', '🟨', '🟧', '🟥']
    if not ip:
        return ""
    ip = secure_log(ip)
    try:
        octets = [int(b) for b in ip.split('.')]
        h = sum(octets) + octets[-1]
        return f"{colors[h % len(colors)]} {ip}"
    except Exception:
        return f"⬜ {ip}"

def parse_user_agent(ua_str):
    try:
        parsed = parse(ua_str)
        ua = parsed.user_agent
        os_info = parsed.os
        device = parsed.device

        device_family = device.family.lower() if device and device.family else ''

        if device_family in ('spider', 'bot', 'crawler'):
            device_type = 'bot'
        elif device_family == 'smartphone':
            device_type = 'mobile'
        elif device_family == 'tablet':
            device_type = 'tablet'
        elif 'mobile' in ua_str.lower():
            device_type = 'mobile'
        elif device_family and device_family != 'other':
            device_type = 'desktop'
        else:
            device_type = 'desktop'

        parts = []
        if ua and ua.family and ua.family != 'Other':
            ua_str_short = ua.family
            if ua.major:
                ua_str_short += f"/{ua.major}"
            parts.append(ua_str_short)
        if os_info and os_info.family and os_info.family != 'Other':
            os_str = os_info.family
            if os_info.major:
                os_str += f"/{os_info.major}"
            parts.append(os_str)

        if parts:
            short = ' '.join(parts)
        else:
            short = ua_str[:80]
            if len(ua_str) > 80:
                short += '…'
        return device_type, short
    except Exception:
        return 'desktop', ua_str[:80] + ('…' if len(ua_str) > 80 else '')

_bans = {}
_strikes = {}
_strikes_lock = threading.Lock()

def _load_bans():
    global _bans
    try:
        p = BAN_FILE
        if not os.path.isfile(p):
            _bans = {}
            return
        with open(p, 'r') as f:
            data = json.load(f)
        _bans = {}
        now = time.time()
        for ip, ban in data.get("bans", {}).items():
            unban = ban.get("unban_at")
            if isinstance(unban, str):
                unban = datetime.fromisoformat(unban).timestamp()
            if unban and unban > now:
                _bans[ip] = {
                    "unban_at": unban,
                    "banned_at": datetime.fromisoformat(ban["banned_at"]).timestamp() if isinstance(ban.get("banned_at"), str) else ban.get("banned_at", 0),
                    "reason": ban.get("reason", "")
                }
        if len(_bans) < len(data.get("bans", {})):
            _save_bans()
    except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError):
        _bans = {}

def _save_bans():
    tmp = None
    try:
        tmp = BAN_FILE + ".tmp"
        data = {"version": 1, "bans": {}}
        for ip, ban in _bans.items():
            data["bans"][ip] = {
                "unban_at": datetime.fromtimestamp(ban["unban_at"], tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "banned_at": datetime.fromtimestamp(ban["banned_at"], tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "reason": ban["reason"]
            }
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, BAN_FILE)
    except Exception:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass

def _ban_ip(ip, duration, reason):
    now = time.time()
    _bans[ip] = {
        "unban_at": now + duration,
        "banned_at": now,
        "reason": reason
    }
    _save_bans()
    ip_id = get_ip_identifier(ip)
    until = datetime.fromtimestamp(now + duration, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    logger.warning("🚫 %s: banned — %s (until %s)", ip_id, secure_log(reason), until)

def _prune_strikes(ip):
    cutoff = time.time() - STRIKE_WINDOW
    if ip in _strikes:
        _strikes[ip] = [s for s in _strikes[ip] if s["time"] > cutoff]
        if not _strikes[ip]:
            del _strikes[ip]

@app.before_request
def log_request_start():
    g.start_time = time.time()
    if RATE_LIMIT_ENABLED:
        _load_bans()
        ip = request.remote_addr
        if ip and ip in _bans:
            ban = _bans[ip]
            if time.time() < ban["unban_at"]:
                until = datetime.fromtimestamp(ban["unban_at"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                ip_id = get_ip_identifier(ip)
                method = secure_log(request.method)
                path = secure_log(request.path)
                logger.warning("🚫 %s %s %s %d 🔴 banned until %s", ip_id, method, path, 429, until)
                return jsonify({"error": f"Your IP has been banned. Try again after {until}."}), 429

@app.after_request
def log_request_end(response):
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data: blob:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://e621.net; object-src 'none'; base-uri 'self';"
    
    origin = request.headers.get('Origin', '')
    if origin == 'https://tagger.vareniye.dev':
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Max-Age'] = '3600'

    if hasattr(g, 'start_time'):
        duration = (time.time() - g.start_time) * 1000
        status = response.status_code
        method = secure_log(request.method)
        path = secure_log(request.path)
        emoji_status = status_emoji(status)
        ip = secure_log(request.remote_addr)
        ip_id = get_ip_identifier(ip)

        if path == '/':
            raw_ua = secure_log(request.headers.get('User-Agent', 'Unknown'))
            accept_lang = secure_log(request.headers.get('Accept-Language', ''))
            referer = secure_log(request.headers.get('Referer', ''))
            if 'service-worker.js' in referer:
                return response
            flag = get_country_flag(accept_lang)
            flag_part = f" {flag}" if flag else ""
            device_type, ua_short = parse_user_agent(raw_ua)
            device_emoji = {
                'desktop': '💻',
                'mobile': '📱',
                'tablet': '📱',
                'bot': '🤖',
                'other': '❓'
            }.get(device_type, '❓')
            logger.info(
                "👤 %s %s %s %s %s %s %d %s %.1fms",
                ip_id, method, path, flag_part, device_emoji, ua_short,
                status, emoji_status, duration
            )
            return response

        if path == '/health' and status == 200:
            if LOG_LEVEL == logging.DEBUG:
                logger.debug("🔄 %s %s %s %d %s %.1fms", ip_id, method, path, status, emoji_status, duration)
        elif path == '/predict':
            logger.info("📤 %s %s %s %d %s %.1fms", ip_id, method, path, status, emoji_status, duration)
        elif LOG_LEVEL == logging.DEBUG:
            logger.debug("📄 %s %s %s %d %s %.1fms", ip_id, method, path, status, emoji_status, duration)
        elif status >= 400:
            logger.warning("⚠️ %s %s %s %d %s %.1fms", ip_id, method, path, status, emoji_status, duration)

        if RATE_LIMIT_ENABLED and response.status_code == 404:
            rip = request.remote_addr
            if rip:
                now = time.time()
                with _strikes_lock:
                    _prune_strikes(rip)
                    _strikes.setdefault(rip, []).append({"path": path, "time": now})
                    strike_count = len(_strikes[rip])
                if strike_count >= BAN_5_STRIKES_THRESHOLD:
                    _ban_ip(rip, BAN_5_STRIKES_DURATION, f"{strike_count}+ 404 offenses (5+ strike threshold)")
                elif strike_count == BAN_3_STRIKES_THRESHOLD:
                    _ban_ip(rip, BAN_3_STRIKES_DURATION, f"{strike_count} 404 offenses (3 strike threshold)")
    return response

if SAVE_UPLOADS:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    logger.info("📁 Upload saving enabled, directory: %s", UPLOAD_DIR)

startup_time = time.time()
logger.info("🚀 e621tagger version: %s", APP_VERSION)
logger.info("⚙️ Loading model on %s...", DEVICE)

model = hydra_load_model(MODEL_PATH)

if DEVICE == 'cpu':
    model = model.float()
    logger.info("🔧 Converted model to float32 for CPU inference")
else:
    model = model.to(dtype=torch.bfloat16, device=DEVICE)

model.requires_grad_(False)
model.eval()
tag_list = [label.label for label in model.labels]
logger.info("✅ Model loaded, %d tags", len(tag_list))

elapsed = (time.time() - startup_time) * 1000
logger.info("⏱️ Worker ready in %.0fms", elapsed)

def is_valid_image(file):
    try:
        file.seek(0)
        img = Image.open(file)
        img.verify()
        file.seek(0)
        return True
    except Exception:
        return False

def is_allowed_file(filename, content_type):
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS and content_type in ALLOWED_MIME_TYPES

def detect_meta_tags_for_image_path(image_path: str):
    tags = set()
    if not image_path:
        return tags
    try:
        with Image.open(image_path) as im:
            w, h = im.size
            fmt = getattr(im, 'format', None)
            if fmt == 'GIF':
                try:
                    if getattr(im, 'n_frames', 1) > 1:
                        tags.add('animated')
                except Exception:
                    pass
            if w <= 250 and h <= 250:
                tags.add('thumbnail')
            if w <= 500 and h <= 500:
                tags.add('low_res')
            if w >= 1600 or h >= 1200:
                tags.add('hi_res')
            if w >= 3200 or h >= 2400:
                tags.add('absurd_res')
            if (w == 3840 and h == 2160) or (w == 2160 and h == 3840) or (w == 4096 and h == 2160) or (w == 2160 and h == 4096):
                tags.add('4k')
            if w >= 10000 and h >= 10000:
                tags.add('superabsurd_res')
            if w > 0 and h > 0:
                ratio = w / h
                if ratio >= 4 or ratio <= 0.25:
                    tags.add('long_image')
                if ratio <= 0.25:
                    tags.add('tall_image')
                ratios = [
                    ('1:1', 1, 1),
                    ('2:1', 2, 1), ('1:2', 1, 2),
                    ('3:1', 3, 1), ('1:3', 1, 3),
                    ('3:2', 3, 2), ('2:3', 2, 3),
                    ('4:3', 4, 3), ('3:4', 3, 4),
                    ('5:3', 5, 3), ('3:5', 3, 5),
                    ('5:4', 5, 4), ('4:5', 4, 5),
                    ('6:5', 6, 5), ('5:6', 5, 6),
                    ('7:4', 7, 4), ('4:7', 4, 7),
                    ('7:3', 7, 3), ('3:7', 3, 7),
                    ('16:10', 16, 10), ('10:16', 10, 16),
                    ('11:8', 11, 8), ('8:11', 8, 11),
                    ('14:9', 14, 9), ('9:14', 9, 14),
                    ('16:9', 16, 9), ('9:16', 9, 16),
                    ('21:9', 21, 9), ('9:21', 9, 21),
                ]
                for tagname, a, b in ratios:
                    if w * b == h * a:
                        tags.add(tagname)
                if (w * 9 == h * 16) or (w * 10 == h * 16):
                    tags.add('widescreen')
    except Exception:
        pass
    return tags

def save_upload(file, original_filename):
    if not SAVE_UPLOADS:
        return None
    safe_name = secure_filename(original_filename)
    if not safe_name:
        safe_name = f"image_{int(time.time())}.jpg"
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    final_name = f"{date_prefix}_{safe_name}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    save_path = os.path.join(UPLOAD_DIR, final_name)
    if not os.path.abspath(save_path).startswith(os.path.abspath(UPLOAD_DIR)):
        logger.error("🔒 Path traversal attempt: %s", save_path)
        return None
    file.seek(0)
    file.save(save_path)
    logger.info("📁 Uploaded file saved to %s", save_path)
    return save_path

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    logger.warning("⚠️ File too large (max 20MB)")
    return jsonify({'error': 'File too large. Maximum size is 20MB.'}), 413

@app.route('/')
def index():
    return render_template('index.html', APP_VERSION=APP_VERSION)

@app.route('/favicon.ico')
def favicon():
    response = make_response(send_from_directory('static', 'favicon.ico'))
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response

@app.route('/static/<path:filename>')
def static_files(filename):
    response = make_response(send_from_directory('static', filename))
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response

@app.route('/service-worker.js')
def service_worker():
    response = make_response(render_template('service-worker.js', APP_VERSION=APP_VERSION))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/health')
def health():
    try:
        if model is None or tag_list is None or len(tag_list) == 0:
            logger.warning("⚠️ Health check: model not loaded (version %s)", APP_VERSION)
            return jsonify({'status': 'unhealthy', 'reason': 'model not loaded'}), 503
        if LOG_LEVEL == logging.DEBUG:
            logger.debug("✅ Health check ok (%d tags, version %s)", len(tag_list), APP_VERSION)
        return jsonify({
            'status': 'healthy',
            'model': model.name,
            'tags_count': len(tag_list),
            'version': APP_VERSION
        }), 200
    except Exception as e:
        logger.exception("💥 Health check failed (version %s)", APP_VERSION)
        return jsonify({'status': 'unhealthy', 'reason': 'internal error'}), 503

@app.route('/predict', methods=['POST', 'OPTIONS'])
@limiter.limit("20 per minute")
def predict():
    if request.method == 'OPTIONS':
        return make_response('', 204)

    ip = secure_log(request.remote_addr)
    ip_id = get_ip_identifier(ip)

    if 'image' not in request.files:
        logger.warning("⚠️ %s: request without image file", ip_id)
        return jsonify({'error': 'No image provided'}), 400

    file = request.files['image']
    if file.filename == '':
        logger.warning("⚠️ %s: empty filename", ip_id)
        return jsonify({'error': 'Empty filename'}), 400

    filename = secure_log(file.filename)
    content_type = file.content_type or ''
    content_type = secure_log(content_type)

    if not is_allowed_file(filename, content_type):
        logger.warning("⚠️ %s: rejected file (type: %s) '%s'", ip_id, content_type, filename)
        return jsonify({'error': 'File type not allowed'}), 400

    if not is_valid_image(file):
        logger.warning("⚠️ %s: rejected invalid image '%s'", ip_id, filename)
        return jsonify({'error': 'Invalid or corrupted image file'}), 400

    logger.info("📥 %s: uploading file '%s'", ip_id, filename)

    top_k_str = request.form.get('top_k', str(DEFAULT_TOP_K))
    try:
        top_k = int(top_k_str)
    except ValueError:
        top_k = DEFAULT_TOP_K
    if top_k not in ALLOWED_TOP_K:
        top_k = DEFAULT_TOP_K

    saved_path = None
    temp_path = None
    try:
        if SAVE_UPLOADS:
            saved_path = save_upload(file, filename)
            if saved_path is None:
                raise Exception("Failed to save uploaded file")
            image_path = saved_path
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                file.seek(0)
                file.save(tmp.name)
                temp_path = tmp.name
            image_path = temp_path

        img_tensor = model.load_image(image_path)
        h = img_tensor.shape[0] // PATCH_SIZE
        w = img_tensor.shape[1] // PATCH_SIZE

        patches = hydra_image.patchify(img_tensor, PATCH_SIZE)
        sizes = torch.tensor([[h, w]], dtype=torch.int32)

        patches = model.from_srgb(patches)
        patches = patches.to(device=DEVICE)
        sizes = sizes.to(device=DEVICE)

        with torch.no_grad():
            logits = model.forward(patches, sizes)

        probs = torch.sigmoid(logits[0].float()).cpu()
        values, indices = probs.topk(top_k)

        tags_with_probs = []
        for idx, val in zip(indices, values):
            label = model.labels[int(idx.item())]
            prob = val.item()
            if label.subcategory and label.subcategory in SUBCATEGORY_DISPLAY_NAMES:
                category_name = SUBCATEGORY_DISPLAY_NAMES[label.subcategory]
            else:
                category_name = TAG_CATEGORIES.get(label.category, label.category.title())
            tags_with_probs.append({
                'tag': label.label,
                'prob': prob,
                'category': category_name
            })

        auto_tags = set()
        try:
            if image_path:
                auto_tags = detect_meta_tags_for_image_path(image_path)
        except Exception:
            auto_tags = set()

        logger.info("✅ %s: file '%s' processed, top %d tags (auto %d)", ip_id, filename, len(tags_with_probs), len(auto_tags))
        return jsonify({
            'success': True,
            'tags': tags_with_probs,
            'auto_meta': sorted(list(auto_tags))
        })
    except Exception as e:
        logger.error("❌ %s: error processing file '%s': %s", ip_id, filename, str(e))
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if temp_path is not None:
            os.unlink(temp_path)

@app.route('/robots.txt')
def robots():
    content = """User-agent: *
Disallow: /predict
Disallow: /health
Disallow: /service-worker.js

Sitemap: https://www.tagger.fenrir784.app/sitemap.xml
"""
    return make_response(content, 200, {'Content-Type': 'text/plain'})

@app.route('/sitemap.xml')
def sitemap():
    lastmod = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.tagger.fenrir784.app/</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    return make_response(content, 200, {'Content-Type': 'application/xml'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
