# JTP-3 Hydra Model Architecture

This document provides comprehensive documentation of the JTP-3 Hydra model architecture. It is designed for ML/inference agents that need to understand the model's components, data flow, and extension system.

## Model Overview

| Attribute | Value |
|-----------|-------|
| **Architecture** | `naflexvit_so400m_patch16_siglip+rr_hydra` (NaFlexViT + HydraPool) |
| **Base Model** | SigLIP-400m (So400m) |
| **Tags Supported** | 7,500+ |
| **Patch Size** | 16x16 pixels |
| **Sequence Length** | Up to 1024 patches |
| **Model Source** | HuggingFace `RedRocket/JTP-3` |

## Architecture Components

### High-Level Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│                    JTP-3 Hydra Model                         │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              NaFlexVit Backbone                      │  │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐        │   │
│  │  │  embeds  │─▶│  27      │─▶│  norm   │        │   │
│  │  │  (patch +│  │  Blocks  │  │        │        │   │
│  │  │  pos)   │  │  (ViT)   │  │        │        │   │
│  │  └───────────┘  └───────────┘  └───────────┘        │   │
│  └───────────────────────┬───────────────────────────────┘   │
│                          │                                   │
│                          ▼ (image_features)                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              HydraPool Classifier Head                 │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐        │   │
│  │  │  q (learned│  │ attention│─▶│ out_proj │─▶ logits│   │
│  │  │  queries)│  │   pool   │  │         │        │   │
│  │  └───────────┘  └───────────┘  └───────────┘        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## NaFlexVit Backbone

The NaFlexVit is a flexible Vision Transformer based on SigLIP-400m, modified for variable sequence length support.

### Implementation

**File**: `siglip2.py`

### Components

```
NaFlexVit
├── embeds (NaFlexEmbeds)
│   ├── pos_embed: Learned positional embeddings (1x16x16x1152)
│   └── proj: Linear(768 → 1152)
├── blocks: ModuleList[27 × NaFlexBlock]
│   ├── attn (NaFlexAttn)
│   │   ├── qkv: Linear(1152, 3456)  # Q,K,V split into 3×1152
│   │   └── proj: Linear(1152, 1152)
│   ├── mlp (NaFlexMlp)
│   │   ├── fc1: Linear(1152, 4304)
│   │   └── fc2: Linear(4304, 1152)
│   ├── norm1: LayerNorm(1152)
│   └── norm2: LayerNorm(1152)
└── norm: LayerNorm(1152)
```

### Forward Methods

| Method | Description |
|--------|-------------|
| `forward()` | Full forward pass |
| `forward_intermediates()` | Return intermediate layer outputs |
| `forward_features()` | Return features without classification |
| `forward_head()` | Apply classification head |

### Variable Sequence Length Support

The model supports variable sequence lengths (not fixed to images):

```python
# Standard forward - fixed sequence
def forward(self, patches, patch_coord, patch_valid):
    output = self.forward_intermediates(patches, patch_coord, patch_valid, [])
    return self.forward_head(output["image_features"], output["patch_valid"])

# Variable length forward
def forward_varlen(self, patches, patch_coord, max_seq=None):
    output = self.forward_intermediates_varlen(patches, patch_coord, max_seq, [])
    return self.forward_head_varlen(
        output["image_features"],
        output["cu_seq"],
        output["max_seq"]
    )
```

### Key Dimensions

| Component | Dimension |
|----------|-----------|
| Input Patches | (batch, seq_len, 768) |
| Hidden Dimension | 1152 |
| Attention Heads | 16 |
| Head Dimension | 1152 / 16 = 72 |
| MLP Hidden | 4304 (×3.75) |
| Number of Blocks | 27 |
| Output Features | (batch, seq_len, 1152) |

---

## HydraPool Classifier Head

HydraPool is a novel attention-based classification head that learns per-tag queries for multi-label classification.

### Implementation

**File**: `hydra_pool.py`

### Architecture

```
HydraPool
├── q: Parameter(n_heads, n_classes, head_dim)
│   # Learned query vectors per tag
├── kv: Linear(input_dim, attn_dim × 2)
│   # Key-Value projection (tie_kv option)
├── qk_norm: RMSNorm(head_dim)
│   # Query/key normalization
├── ff_norm: LayerNorm(attn_dim)
├── ff_in: Linear(attn_dim, hidden_dim × 2)
│   # SwiGLU feedforward
├── ff_act: SwiGLU()
├── ff_drop: Dropout(ff_dropout)
├── ff_out: Linear(hidden_dim, attn_dim)
├── mid_blocks: ModuleList[n × _MidBlock]
│   # Optional mid-level processing blocks
└── out_proj: BatchLinear(n_classes, attn_dim, output_dim × 2)
    # Per-class output projection
```

### Forward Process

```python
def forward(self, x, attn_mask=None):
    # x: (batch, seq_len, attn_dim)
    
    # 1. Attention pooling
    x, k, v = self._forward_attn(x, attn_mask)
    
    # 2. Feedforward
    x = self._forward_ff(x)
    
    # 3. Mid blocks (if any)
    for block in self.mid_blocks:
        x = block(x, k, v, attn_mask)
    
    # 4. Output projection
    x = self._forward_out(x)
    
    return x  # (batch, n_classes, output_dim)
```

### Attention Mechanism

```python
def _forward_attn(self, x, attn_mask):
    # x: (batch, seq_len, attn_dim)
    
    # 1. Expand learned queries to batch size
    q = self._forward_q().expand(*x.shape[:-2], -1, -1, -1)
    # q: (batch, n_heads, n_classes, head_dim)
    
    # 2. Compute KV from features
    x = self.kv(x)
    k, v = rearrange(x, "... s (n h e) -> n ... h s e", n=2).unbind(0)
    # k, v: (batch, n_heads, seq_len, head_dim)
    
    # 3. Normalize keys
    k = self.qk_norm(k)
    
    # 4. Scaled dot-product attention
    x = scaled_dot_product_attention(q, k, v, attn_mask=attn_mask)
    # x: (batch, n_heads, n_classes, head_dim)
    
    return rearrange(x, "... h s e -> ... s (h e)"), k, v
```

### Inference Optimization

The HydraPool normalizes queries during inference for faster execution:

```python
def inference(self):
    # Normalize q vectors at inference time
    with torch.no_grad():
        self.q.copy_(self._forward_q())
    self._q_normed = True
    return self
```

---

## Image Processing Pipeline

### Overview

```
Input Image → EXIF handling → sRGB conversion → Resize → Patchify → Model Input
```

### Implementation

**File**: `image.py`

### Steps

#### 1. EXIF Orientation

```python
exif_transpose(img, in_place=True)
```

Corrects image rotation based on EXIF data.

#### 2. Color Profile Conversion

```python
# Convert to sRGB for consistent color handling
profileToProfile(img, input_profile, sRGB_profile,
                renderingIntent=RELATIVE_COLORIMETRIC,
                inPlace=True)
```

#### 3. Mode Conversion

```python
# Ensure RGB mode
if img.has_transparency_data:
    img = img.convert("RGBa")  # RGBA if transparency
else:
    img = img.convert("RGB")    # RGB otherwise
```

#### 4. Resize (Sequence Length Constraint)

**File**: `model.py`

```python
def get_image_size_for_seq(image_hw, patch_size=16, max_seq_len=1024, ...):
    """Determine max image size within sequence constraint."""
    
    h, w = image_hw
    max_py = max((h * max_ratio) // patch_size, 1)
    max_px = max((w * max_ratio) // patch_size, 1)
    
    if (max_py * max_px) <= max_seq_len:
        return max_py * patch_size, max_px * patch_size
    
    # Binary search for aspect-ratio-preserving size
    ...
```

#### 5. Patch Extraction

```python
def patchify_image(img, patch_size=16, ...):
    # Rearrange: (H, W, C) → (H/p × W/p, p×p×C)
    patches = rearrange(
        np.asarray(img)[:, :, :3],
        "(h p1) (w p2) c -> h w (p1 p2 c)",
        p1=patch_size, p2=patch_size
    )
    
    # Create coordinates
    coords = np.stack(np.meshgrid(
        np.arange(patches.shape[0]),
        np.arange(patches.shape[1]),
        indexing='ij'
    ), axis=-1)
    
    return patches, coords, valid_mask
```

### Output Tensors

| Tensor | Shape | Dtype | Description |
|-------|-------|-------|-------------|
| `patches` | (seq_len, 768) | uint8 | Pixel values (RGB × 16×16) |
| `patch_coords` | (seq_len, 2) | int16 | (y, x) positions |
| `patch_valid` | (seq_len,) | bool | Valid patch mask |

### Example

```python
from model import load_image

# Load and process image
patches, patch_coords, patch_valid = load_image(
    "artwork.png",
    patch_size=16,
    max_seq_len=1024,
    share_memory=False
)

print(f"Patches: {patches.shape}")      # (~1024, 768)
print(f"Coords: {patch_coords.shape}")  # (1024, 2)
print(f"Valid: {patch_valid.shape}")  # (1024,)
```

---

## Model Inference

### Complete Inference Flow

```python
import torch
from model import load_model, load_image

# 1. Load model
model, tag_list, ext_info = load_model(
    "models/jtp-3-hydra.safetensors",
    device="cuda"
)
model.eval()

# 2. Load and process image
patches, patch_coords, patch_valid = load_image(
    "artwork.png",
    patch_size=16,
    max_seq_len=1024
)

# 3. Prepare input
p_d = patches.unsqueeze(0).to("cuda")
pc_d = patch_coords.unsqueeze(0).to("cuda")
pv_d = patch_valid.unsqueeze(0).to("cuda")

# Normalize: [0, 255] → [-1, 1]
p_d = p_d.to(dtype=torch.bfloat16).div_(127.5).sub_(1.0)
pc_d = pc_d.to(dtype=torch.int32)

# 4. Run inference
with torch.no_grad():
    logits = model(p_d, pc_d, pv_d)

# 5. Process outputs
probs = torch.sigmoid(logits[0].float()).cpu()
values, indices = probs.topk(200)

# 6. Get tag predictions
tags_with_probs = []
for idx, val in zip(indices, values):
    tag = tag_list[idx.item()]
    prob = val.item()
    tags_with_probs.append({"tag": tag, "prob": prob})
```

### Output

| Variable | Type | Description |
|----------|-----|-------------|
| `logits` | Tensor (1, num_tags) | Raw model outputs |
| `probs` | Tensor (num_tags,) | Sigmoid probabilities (0-1) |
| `tags_with_probs` | List[dict] | Top-K predictions sorted by probability |

---

## Extension System

Extensions allow adding new classification tags to the model without retraining.

### Extension Format

- **File Format**: SAFETENSORS
- **Required Metadata**:
  - `modelspec.implementation`: `redrocket.extension.label.v1`
  - `modelspec.architecture`: Must match base model
  - `classifier.label`: Tag name
  - `classifier.label.category`: Category (general, artist, etc.)
  - `classifier.label.implies`: Space-separated implied tags

### Extension Weights

| Key | Shape | Description |
|-----|-------|-------------|
| `q` | (1, 1, head_dim) | Query vector |
| `out_proj.weight` | (1, attn_dim, output_dim×2) | Output projection |
| `mid_blocks.{n}.q_cls` | (1, n_heads, head_dim) | Mid block queries |

### Loading Extensions

```python
from model import load_model, discover_extensions

# Load model with extensions
model, tags, ext_info = load_model(
    "models/jtp-3-hydra.safetensors",
    extensions=discover_extensions("extensions/"),
    device="cuda"
)

print(f"Total tags: {len(tags)}")
for path, info in ext_info.items():
    print(f"  {path}: {info['label']}")
```

### Extension Directory Structure

```
extensions/
├── character_tag1.safetensors
├── character_tag2.safetensors
└── species_tag.safetensors
```

---

## CLI Inference

The `inference.py` script provides command-line batch processing.

### Basic Usage

```bash
# Single image (interactive)
python inference.py image.png

# Batch from directory
python inference.py -r -o output.csv images/

# With options
python inference.py -t 0.2 -i inherit -x artist image.png

# CUDA
python inference.py -d cuda image.png
```

### Arguments

| Argument | Description |
|----------|-------------|
| `-t`, `--threshold` | Classification threshold (-1.0 to 1.0) or calibration CSV path |
| `-i`, `--implications` | Implication mode (inherit, constrain, remove, constrain-remove, off) |
| `-x`, `--exclude` | Exclude category (may specify multiple) |
| `-b`, `--batch` | Batch size |
| `-w`, `--workers` | Number of dataloader workers |
| `-S`, `--seqlen` | NaFlex sequence length (64-2048) |
| `-d`, `--device` | PyTorch device (cuda, cpu) |
| `-r`, `--recursive` | Process directories recursively |
| `-o`, `--output` | Output CSV path or '-' for stdout |
| `-p`, `--prefix` | Prefix for caption files |
| `-M`, `--model` | Model file path |
| `-m`, `--metadata` | Tag metadata CSV path |
| `-e`, `--extension` | Extension path (may specify multiple) |

### Output Formats

**Text Captions** (default):

```
blue_eyes, anthro, female, furry, smile
```

**CSV** (-o output.csv):

```csv
filename,tag1,tag2,tag3,...
image1.png,0.95,0.87,0.82,...
image2.png,0.91,0.78,0.65,...
```

---

## Calibration

Calibration files adjust per-tag thresholds for better precision/recall balance.

### Format

```csv
tag,threshold
female,0.55
anthro,0.50
furry,0.45
```

### Usage

```bash
python inference.py -t calibration.csv image.png
```

### Threshold Modes

| Mode | Description |
|------|-------------|
| `-1.0 to 1.0` | Symmetric threshold (0 = 50% probability) |
| `calibration.csv` | Per-tag thresholds |

### Threshold Conversion

The symmetric threshold uses logits internally. Values are converted between probability space and logit space:

```python
# inference.py - conversion functions
def from_symmetric(t: float) -> float:
    """Convert symmetric threshold (-1.0 to 1.0) to probability (0.0 to 1.0)."""
    return torch.sigmoid(torch.tensor(t)).item()

def to_symmetric(p: float) -> float:
    """Convert probability (0.0 to 1.0) to symmetric threshold (-1.0 to 1.0)."""
    return torch.logit(torch.tensor(p)).item()
```

Example:
| Symmetric | Probability |
|----------|-------------|
| -1.0 | ~26.9% |
| 0.0 | 50.0% |
| 1.0 | ~73.1% |

### Tag Rewriting

By default, certain tags are rewritten for e621 compatibility:

```python
# inference.py - rewrite_tag function
def rewrite_tag(tag: str) -> str:
    if not args.original_tags:
        tag = tag.replace("vulva", "pussy")
    return tag
```

| Original | Rewritten | Flag to Keep Original |
|----------|-----------|---------------------|
| `vulva` | `pussy` | `--original-tags` |

---

## Model Loading Details

### From safetensors

```python
from safetensors import safe_open

with safe_open(path, framework="pt", device="cpu") as f:
    metadata = f.metadata()
    state_dict = {key: f.get_tensor(key) for key in f.keys()}

# Extract metadata
arch = metadata["modelspec.architecture"]
labels = metadata["classifier.labels"].split("\n")
```

### Model Metadata

| Key | Description |
|-----|-------------|
| `modelspec.architecture` | Model architecture string |
| `modelspec.implementation` | Implementation identifier |
| `classifier.labels` | Newline-separated tag names |

---

## Performance Considerations

### Memory Usage

| Component | GPU Memory |
|-----------|-----------|
| JTP-3 Model (bfloat16) | ~2GB |
| Input (batch=1) | ~50MB |
| Gradients | ~0 (inference) |
| **Total (single worker, CUDA)** | ~2.1GB |

### Multi-Worker Memory Scaling

Each Gunicorn worker runs its own Flask process with a separate model load:

| Workers | GPU Memory |
|---------|------------|
| 1 | ~2.1GB |
| 2 | ~4.2GB |
| 4 | ~8.4GB |

For production deployments, ensure your GPU has enough VRAM for the number of workers (recommended: 4GB per worker minimum).

### Inference Speed

| Device | Approximate Time |
|--------|-----------------|
| RTX 4090 | ~100ms |
| RTX 3090 | ~150ms |
| CPU (i9-13900K) | ~2000ms |

### Optimization Flags

```python
# Enable TF32 on Ampere+
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# bfloat16 inference
model = model.to(dtype=torch.bfloat16)
```

---

## Integration with Flask

The Flask app in `app.py` wraps the model:

```python
from model import load_model, load_image

# Load on startup
MODEL_PATH = os.getenv('MODEL_PATH', 'models/jtp-3-hydra.safetensors')
DEVICE = os.getenv('DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')

model, tag_list, ext_info = load_model(MODEL_PATH, device=DEVICE)

if DEVICE == 'cpu':
    model = model.float()
else:
    model = model.to(dtype=torch.bfloat16)

model.requires_grad_(False)
model.eval()

# In predict route:
patches, patch_coords, patch_valid = load_image(image_path, ...)
p_d = patches.unsqueeze(0).to(DEVICE)
# ... inference ...
```