import os
import tempfile
import logging
import time
import re
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template, send_from_directory, make_response, g
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import torch
from PIL import Image

from model import load_model, load_image
from inference import load_metadata

TAG_CATEGORIES = {
    0: "General",
    1: "Artist",
    3: "Copyright",
    4: "Character",
    5: "Species",
    7: "Meta",
    8: "Lore",
}

APP_VERSION = os.getenv('APP_VERSION', 'test')
LOG_LEVEL = logging.DEBUG if APP_VERSION.startswith('test-') else logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
logging.getLogger("PIL").setLevel(logging.WARNING)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

if os.getenv('USE_PROXY', 'false').lower() == 'true':
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["500 per hour"],
    storage_uri="memory://",
)

MODEL_PATH = os.getenv('MODEL_PATH', 'models/jtp-3-hydra.safetensors')
TAGS_PATH = os.getenv('TAGS_PATH', 'data/jtp-3-hydra-tags.csv')
DEVICE = os.getenv('DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')
MAX_SEQ_LEN = int(os.getenv('MAX_SEQ_LEN', '1024'))
PATCH_SIZE = 16
DEFAULT_TOP_K = 200
ALLOWED_TOP_K = {50, 75, 100, 150, 200, 250}

SAVE_UPLOADS = os.getenv('SAVE_UPLOADS', 'false').lower() == 'true'
UPLOAD_DIR = os.getenv('UPLOAD_DIR', '/app/uploads')
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff'}

def secure_log(s: str) -> str:
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

@app.before_request
def log_request_start():
    g.start_time = time.time()

@app.after_request
def log_request_end(response):
    if hasattr(g, 'start_time'):
        duration = (time.time() - g.start_time) * 1000
        status = response.status_code
        method = secure_log(request.method)
        path = secure_log(request.path)
        emoji = status_emoji(status)

        if path == '/':
            ip = secure_log(request.remote_addr)
            ua = secure_log(request.headers.get('User-Agent', 'Unknown'))
            accept_lang = secure_log(request.headers.get('Accept-Language', ''))
            referer = secure_log(request.headers.get('Referer', ''))
            if 'service-worker.js' in referer:
                return response
            flag = get_country_flag(accept_lang)
            flag_part = f" {flag}" if flag else ""
            logger.info(
                "👤 %s %s ip=%s%s ua=%s status=%d %s duration=%.1fms",
                method, path, ip, flag_part, ua[:100] + '...' if len(ua) > 100 else ua,
                status, emoji, duration
            )
            return response

        if path == '/health' and status == 200:
            if LOG_LEVEL == logging.DEBUG:
                logger.debug("🔄 %s %s status=%d %s duration=%.1fms", method, path, status, emoji, duration)
        elif path == '/predict':
            logger.info("📤 %s %s status=%d %s duration=%.1fms", method, path, status, emoji, duration)
        elif LOG_LEVEL == logging.DEBUG:
            logger.debug("📄 %s %s status=%d %s duration=%.1fms", method, path, status, emoji, duration)
        elif status >= 400:
            logger.warning("⚠️ %s %s status=%d %s duration=%.1fms", method, path, status, emoji, duration)
    return response

if SAVE_UPLOADS:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    logger.info("📁 Upload saving enabled, directory: %s", UPLOAD_DIR)

startup_time = time.time()
logger.info("🚀 e621tagger version: %s", APP_VERSION)
logger.info("⚙️ Loading e621tagger model on %s...", DEVICE)
model, tag_list, ext_info = load_model(MODEL_PATH, device=DEVICE)

if DEVICE == 'cpu':
    model = model.float()
    logger.info("🔧 Converted model to float32 for CPU inference")
else:
    model = model.to(dtype=torch.bfloat16)

model.requires_grad_(False)
model.eval()
logger.info("✅ Model loaded, %d tags", len(tag_list))

logger.info("📚 Loading tag metadata...")
metadata = load_metadata(TAGS_PATH)
logger.info("✅ Metadata loaded, %d entries", len(metadata))

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
    return send_from_directory('static', 'favicon.ico')

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
            logger.warning("⚠️ Health check: model not loaded")
            return jsonify({'status': 'unhealthy', 'reason': 'model not loaded'}), 503
        if LOG_LEVEL == logging.DEBUG:
            logger.debug("✅ Health check ok (tags=%d)", len(tag_list))
        return jsonify({
            'status': 'healthy',
            'model': 'loaded',
            'tags_count': len(tag_list),
            'version': APP_VERSION
        }), 200
    except Exception as e:
        logger.exception("💥 Health check failed")
        return jsonify({'status': 'unhealthy', 'reason': 'internal error'}), 503

@app.route('/predict', methods=['POST'])
@limiter.limit("20 per minute")
def predict():
    ip = secure_log(request.remote_addr)

    if 'image' not in request.files:
        logger.warning("⚠️ IP=%s: request without image file", ip)
        return jsonify({'error': 'No image provided'}), 400

    file = request.files['image']
    if file.filename == '':
        logger.warning("⚠️ IP=%s: empty filename", ip)
        return jsonify({'error': 'Empty filename'}), 400

    filename = secure_log(file.filename)
    content_type = file.content_type or ''
    content_type = secure_log(content_type)

    if not is_allowed_file(filename, content_type):
        logger.warning("⚠️ IP=%s: rejected file '%s' (type: %s)", ip, filename, content_type)
        return jsonify({'error': 'File type not allowed'}), 400

    if not is_valid_image(file):
        logger.warning("⚠️ IP=%s: rejected invalid image file '%s'", ip, filename)
        return jsonify({'error': 'Invalid or corrupted image file'}), 400

    logger.info("📥 IP=%s: uploading file '%s'", ip, filename)

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

        patches, patch_coords, patch_valid = load_image(
            image_path,
            patch_size=PATCH_SIZE,
            max_seq_len=MAX_SEQ_LEN,
            share_memory=False
        )
        p_d = patches.unsqueeze(0).to(DEVICE)
        pc_d = patch_coords.unsqueeze(0).to(DEVICE)
        pv_d = patch_valid.unsqueeze(0).to(DEVICE)

        if DEVICE == 'cpu':
            p_d = p_d.to(dtype=torch.float32).div_(127.5).sub_(1.0)
        else:
            p_d = p_d.to(dtype=torch.bfloat16).div_(127.5).sub_(1.0)
        pc_d = pc_d.to(dtype=torch.int32)

        with torch.no_grad():
            logits = model(p_d, pc_d, pv_d)

        probs = torch.sigmoid(logits[0].float()).cpu()
        values, indices = probs.topk(top_k)
        tags_with_probs = []
        for idx, val in zip(indices, values):
            tag = tag_list[idx.item()]
            prob = val.item()
            cat_id = metadata.get(tag, (-1, []))[0]
            category_name = TAG_CATEGORIES.get(cat_id, "Other")
            tags_with_probs.append({
                'tag': tag,
                'prob': prob,
                'category': category_name
            })
        logger.info("✅ IP=%s: file '%s' processed, top=%d tags", ip, filename, len(tags_with_probs))
        return jsonify({
            'success': True,
            'tags': tags_with_probs
        })
    except Exception as e:
        logger.error("❌ IP=%s: error processing file '%s': %s", ip, filename, str(e))
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if temp_path is not None:
            os.unlink(temp_path)

@app.route('/robots.txt')
def robots():
    content = """User-agent: *
Disallow: /static/
Disallow: /predict
Disallow: /health
Disallow: /service-worker.js

Sitemap: https://www.tagger.fenrir784.ru/sitemap.xml
"""
    return make_response(content, 200, {'Content-Type': 'text/plain'})

@app.route('/sitemap.xml')
def sitemap():
    lastmod = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.tagger.fenrir784.ru/</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    return make_response(content, 200, {'Content-Type': 'application/xml'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
