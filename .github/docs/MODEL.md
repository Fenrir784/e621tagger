# JTP-3 Hydra Model Architecture

This document provides comprehensive documentation of the JTP-3 Hydra model architecture. It is designed for ML/inference agents that need to understand the model's components, data flow, and extension system.

## Model Overview

| Attribute | Value |
|-----------|-------|
| **Architecture** | `naflexvit_so400m_patch16_siglip+rr_hydra2` (NaFlexViT + HydraPool + LinearHead) |
| **Base Model** | SigLIP-400m (So400m) |
| **Tags Supported** | 8,888 (Hydra 3.5) |
| **Patch Size** | 16x16 pixels |
| **Sequence Length** | Up to 1024 patches |
| **Model Source** | HuggingFace `RedRocket/Hydra` |

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
| `forward(x, sizes, valid)` | Full forward pass with stacked patches |
| `forward_features(x, sizes, valid)` | Return features without classification head |
| `forward_head(features, valid)` | Apply attention pool + classification head |
| `forward_varlen(x, sizes, cu_seq, max_seq)` | Variable-length sequence forward |

### Variable Sequence Length Support

The model supports variable sequence lengths via two modes:

```python
# Standard forward - stacked batch (fixed max sequence length)
def forward(self, x, sizes=None, valid=None):
    output = self.forward_features(x, sizes, valid)
    return self.forward_head(output.pop("features"), output.pop("valid"))

# Variable length forward - jagged tensor (efficient for varied sizes)
def forward_varlen(self, x, sizes, cu_seq, max_seq=1024):
    output = self.forward_features_varlen(x, sizes, cu_seq, max_seq)
    return self.forward_head_varlen(output.pop("features"), output.pop("cu_seq"), output.pop("max_seq"))
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

**File**: `pool.py`

### Architecture

```
HydraPool
├── q: Parameter(n_heads, n_classes, head_dim)
│   # Learned query vectors per tag
├── kv: Linear(input_dim, attn_dim × 2)
│   # Key-Value projection
├── qk_norm: RMSNorm(head_dim)
│   # Query/key normalization
├── ff: _FeedForward
│   ├── norm: LayerNorm(attn_dim)
│   ├── proj_in: SwiGLU(attn_dim, ff_dim)
│   └── proj_out: Linear(ff_dim, attn_dim)
├── mid_blocks: ModuleList[n × _MidBlock]
    # Optional mid-level processing blocks
```

### Forward Process

```python
def forward(self, x, attn_mask=None):
    # x: (batch, seq_len, attn_dim)
    
    # 1. Attention pooling
    x, k, v = self._forward_attn(x, attn_mask)
    
    # 2. Feedforward with residual
    x = x + self.ff(x)
    
    # 3. Mid blocks (if any)
    for block in self.mid_blocks:
        x = block(x, k, v, attn_mask)
    
    return x  # (batch, n_classes, attn_dim)
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
    
    # 3. Normalize keys (queries are pre-normalized at init)
    k = self.qk_norm(k)
    
    # 4. Scaled dot-product attention
    x = scaled_dot_product_attention(q, k, v, attn_mask=attn_mask)
    # x: (batch, n_heads, n_classes, head_dim)
    
    return rearrange(x, "... h s e -> ... s (h e)"), k, v
```

### Query Normalization

Queries are pre-normalized at initialization time via `qk_norm` to improve training stability:

```python
with torch.no_grad():
    self.q.copy_(self.qk_norm(self.q))
```

---

## Image Processing Pipeline

### Overview

```
Input Image → Orientation detection → Crop → sRGB conversion → Alpha flatten → Resize → Autorot → Patchify → Model Input
```

### Implementation

**File**: `image.py`, via `_open_profile()` with `open_srgb()` entry point

### Steps

#### 1. Orientation Detection & Crop

EXIF orientation is detected from image metadata. If a crop region is specified, it is applied before color transformation.

#### 2. ICC Color Transform

```python
img = img.icc_transform(
    profile, embedded=True,
    intent=Intent.RELATIVE,
    black_point_compensation=True,
    depth=depth,
)
```

Converts the image to the sRGB profile, respecting embedded ICC profiles.

#### 3. Alpha Flattening

```python
if img.hasalpha():
    img = img.flatten(background=background)
```

If the image has an alpha channel, it is flattened against the configured background color (0 = black, 127 = grey, or 255 = white per `classifier.background` metadata).

#### 4. Resize (via Kernel)

Resizing uses the configured kernel (`Kernel.LANCZOS3` or `Kernel.MKS2013` for linear) and may optionally apply pre/post LUTs for linear-light resizing.

#### 5. Autorotate

```python
img = img.autorot()
```

Applies EXIF rotation after resize.

#### 6. Patch Extraction

Patches are extracted by the `patchify()` function in `image.py` which spreads the image into patches and flattens into a sequence of patch vectors.

#### Resize Sizing Algorithm

**File**: `model.py`

```python
def get_image_size_for_seq(image_size, patch_size=16, max_seq_len=1024, ...):
    """Determine max image size within sequence constraint."""
    
    h, w = image_size
    max_py = int(max((h * max_ratio) // patch_size, 1))
    max_px = int(max((w * max_ratio) // patch_size, 1))
    
    if (max_py * max_px) <= max_seq_len:
        return max_py * patch_size, max_px * patch_size
    
    # Binary search for aspect-ratio-preserving size
    ...
    return py * patch_size, px * patch_size
```

#### Patch Extraction Implementation

**File**: `image.py`, function `patchify()`

```python
def patchify(img, patch_size=16):
    img = spread(img, patch_size)
    return img.flatten(1, 2).flatten(-3)
```

### Output

The image pipeline produces a single tensor (not patches/coords/valid tuple):

| Variable | Type | Description |
|----------|------|-------------|
| `img_tensor` | Tensor (H, W, 3) | Processed image in uint8 (0-255) sRGB |

Patch extraction and stacking happen at inference time via `hydra_image.patchify()` and the model's `from_srgb()` normalization.

### Example

```python
from hydra.model import load_model

model = load_model("models/hydra-3.5.safetensors")

# Load and process image (returns a tensor)
img_tensor = model.load_image("artwork.png")

# Patchify and normalize
patches = hydra_image.patchify(img_tensor, 16)
patches = model.from_srgb(patches)  # uint8 → bfloat16, normalize to [-1, 1]
sizes = torch.tensor([[h, w]], dtype=torch.int32)
```

---

## Model Inference

### Complete Inference Flow

```python
import torch
from hydra import image as hydra_image
from hydra.model import Hydra, load_model

# 1. Load model
model: Hydra = load_model("models/hydra-3.5.safetensors")
model.eval()
model.requires_grad_(False)
tag_list = [label.label for label in model.labels]

# 2. Load and process image
img_tensor = model.load_image("artwork.png")  # returns (H, W, 3) uint8

# 3. Patchify and normalize
h = img_tensor.shape[0] // 16
w = img_tensor.shape[1] // 16
patches = hydra_image.patchify(img_tensor, 16)  # (B, seq, 768)
sizes = torch.tensor([[h, w]], dtype=torch.int32)

# Normalize: [0, 255] → [-1, 1] (via from_srgb)
patches = model.from_srgb(patches)
patches = patches.to(device="cuda")
sizes = sizes.to(device="cuda")

# 4. Run inference
with torch.no_grad():
    logits = model.forward(patches, sizes)  # (1, num_tags)

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
  - `modelspec.implementation`: `redrocket.extension.label.v1` or `v2`
  - `modelspec.architecture`: Must match base model
  - `classifier.label`: Tag name
  - `classifier.label.category`: Category ID (0-8, 100-111)
  - `classifier.label.implies`: Space-separated implied tags

### Extension Weights

| Key | Shape | Description |
|-----|-------|-------------|
| `q` | (1, 1, head_dim) | Query vector |
| `out_proj.weight` (saved) → loaded as `head.proj.weight` | (1, attn_dim, 2) | SwiGLU output projection |
| `mid_blocks.{n}.q_cls` | (1, n_heads, head_dim) | Mid block queries |

### Loading Extensions

```python
from hydra.model import Hydra, load_model, Extension

# Load model with extensions
model: Hydra = load_model("models/hydra-3.5.safetensors")
model.load_extensions(Extension.discover("extensions/"))

print(f"Total tags: {len(model.labels)}")
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
from hydra.model import load_model
from hydra import image as hydra_image

# Load on startup
MODEL_PATH = os.getenv('MODEL_PATH', 'models/hydra-3.5.safetensors')
DEVICE = os.getenv('DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')
PATCH_SIZE = 16

model = load_model(MODEL_PATH)

if DEVICE == 'cpu':
    model = model.float()
else:
    model = model.to(dtype=torch.bfloat16, device=DEVICE)

model.requires_grad_(False)
model.eval()

# In predict route:
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
```