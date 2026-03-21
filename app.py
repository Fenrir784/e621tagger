import os
import tempfile
import logging
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

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

if SAVE_UPLOADS:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    logger.info(f"Upload saving enabled, directory: {UPLOAD_DIR}")

logger.info(f"Loading e621tagger model on {DEVICE}...")
model, tag_list, ext_info = load_model(MODEL_PATH, device=DEVICE)

if DEVICE == 'cpu':
    model = model.float()
    logger.info("Converted model to float32 for CPU inference")
else:
    model = model.to(dtype=torch.bfloat16)

model.requires_grad_(False)
model.eval()
logger.info(f"Model loaded, {len(tag_list)} tags")

logger.info("Loading tag metadata...")
metadata = load_metadata(TAGS_PATH)
logger.info(f"Metadata loaded, {len(metadata)} entries")

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
        logger.error(f"Path traversal attempt: {save_path}")
        return None
    file.seek(0)
    file.save(save_path)
    logger.info(f"Uploaded file saved to {save_path}")
    return save_path

@app.before_request
def log_request_info():
    if request.path == '/' or request.path == '/predict':
        ip = request.remote_addr
        ua = request.headers.get('User-Agent', 'Unknown')
        if len(ua) > 100:
            ua = ua[:100] + '...'
        logger.info(f"Client connected: IP={ip}, UA={ua}, Path={request.path}")

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 20MB.'}), 413

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')

@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('static', 'service-worker.js')

@app.route('/predict', methods=['POST'])
@limiter.limit("20 per minute")
def predict():
    ip = request.remote_addr
    if 'image' not in request.files:
        logger.warning(f"IP={ip}: request without image file")
        return jsonify({'error': 'No image provided'}), 400
    file = request.files['image']
    if file.filename == '':
        logger.warning(f"IP={ip}: empty filename")
        return jsonify({'error': 'Empty filename'}), 400
    filename = file.filename
    content_type = file.content_type or ''
    if not is_allowed_file(filename, content_type):
        logger.warning(f"IP={ip}: rejected file '{filename}' (type: {content_type})")
        return jsonify({'error': 'File type not allowed'}), 400
    if not is_valid_image(file):
        logger.warning(f"IP={ip}: rejected invalid image file '{filename}'")
        return jsonify({'error': 'Invalid or corrupted image file'}), 400
    logger.info(f"IP={ip}: uploading file '{filename}'")
    saved_path = save_upload(file, filename)

    top_k_str = request.form.get('top_k', str(DEFAULT_TOP_K))
    try:
        top_k = int(top_k_str)
    except ValueError:
        top_k = DEFAULT_TOP_K
    if top_k not in ALLOWED_TOP_K:
        top_k = DEFAULT_TOP_K

    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
        file.seek(0)
        file.save(tmp.name)
        temp_path = tmp.name
    try:
        patches, patch_coords, patch_valid = load_image(
            temp_path,
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
        logger.info(f"IP={ip}: file '{filename}' processed successfully, top {len(tags_with_probs)} tags")
        return jsonify({
            'success': True,
            'tags': tags_with_probs
        })
    except Exception as e:
        logger.error(f"IP={ip}: error processing file '{filename}': {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        os.unlink(temp_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
