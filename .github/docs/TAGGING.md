# Tag Classification and Implications

This document provides comprehensive documentation of the tag classification system used by e621tagger. It covers tag categories, implication logic, threshold handling, and output presentation.

## Tag System Overview

e621tagger classifies images using 7,500+ tags organized into e621 categories. Tags are assigned confidence scores and can have implications (hierarchical relationships) that affect final output.

```
┌─────────────────────────────────────────────────────────────┐
│                 Tag Classification System               │
│                                                        │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Raw Model Output (7500+ logits)               │    │
│  └──────────────────────┬────────────────────────┘    │
│                           │                            │
│                           ▼                            │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Sigmoid Activation (0.0 - 1.0)              │    │
│  └──────────────────────┬────────────────────────┘    │
│                           │                            │
│                           ▼                            │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Implication Application                     │    │
│  │  - Inherit, Constrain, Remove                │    │
│  └──────────────────────┬────────────────────────┘    │
│                           │                            │
│                           ▼                            │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Threshold Filtering                         │    │
│  │  - Category exclusion                      │    │
│  │  - Per-tag thresholds                       │    │
│  └──────────────────────┬────────────────────────┘    │
│                           │                            │
│                           ▼                            │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Top-K Selection                           │    │
│  └──────────────────────┬────────────────────────┘    │
│                           │                            │
│                           ▼                            │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Category + Meta Tag Assignment             │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Tag Categories

Tags are organized into e621 categories with numeric IDs:

### Category Mapping

| Category ID | Name | Description | Example Tags |
|-------------|------|-------------|--------------|
| 0 | General | General subject matter | `female`, `male`, `anthro`, `solo` |
| 1 | Artist | Artist names | `artist:fenrir784`, `oc:request` |
| 3 | Copyright | Series/franchise | `sonic_the_hedgehog`, `nintendo` |
| 4 | Character | Fictional characters | `miles_tails_prower` |
| 5 | Species | Species/body types | `wolf`, `dragon`, `fox` |
| 7 | Meta | Rating and technical | `safe`, `questionable`, `hi_res` |
| 8 | Lore | Story elements | `backstory`, `backview` |
| - | Other | Tags from unrecognized categories | Legacy or custom tags |

### From Code

```python
# app.py
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

---

## Implication System

Tags can imply other tags in hierarchical relationships. For example:
- `intersex` implies `male` and `female`
- `anthro` implies `humanoid` (in some contexts)
- `masc` implies `male`

### Implication Modes

The CLI supports five modes for handling implications:

| Mode | Description | Behavior |
|------|-------------|----------|
| `inherit` | Tags inherit highest probability | If A implies B, B's prob = max(B's prob, A's prob) |
| `constrain` | Tags constrained to lowest | If A implies B, A's prob = min(A's prob, B's prob) |
| `remove` | Exclude implied tags | Remove all tags that are implied by other tags |
| `constrain-remove` | Combination | Constrain then remove |
| `off` | No implications | Ignore implication relationships |

### Implementation

**File**: `inference.py`

```python
def inherit_implications(labels, antecedent, metadata):
    """Tags inherit highest probability from implied tags."""
    p = labels[antecedent]
    for consequent in metadata.get(antecedent, ()):
        q = labels.get(consequent)
        if q is not None and q < p:
            labels[consequent] = p
        inherit_implications(labels, consequent, metadata)

def constrain_implications(labels, antecedent, metadata):
    """Tags constrained to lowest implied probability."""
    for consequent in metadata.get(antecedent, ()):
        p = labels.get(consequent)
        if p is not None and labels[antecedent] > p:
            labels[antecedent] = p
        constrain_implications(labels, consequent, metadata)

def remove_implications(labels, antecedent, metadata):
    """Remove implied tags."""
    for consequent in metadata.get(antecedent, ()):
        labels.pop(consequent, None)
        remove_implications(labels, consequent, metadata)
```

### Example

Given:
- `female`: 0.9
- `futanari`: 0.8 (implies `female`)
- `intersex`: 0.7 (implies `female` and `male`)

| Mode | female | futanari | intersex | male |
|------|---------|---------|----------|------|
| Off | 0.9 | 0.8 | 0.7 | - |
| Inherit | 0.9 | 0.8→0.9 | 0.7→0.9 | - |
| Constrain | 0.9→0.8 | 0.8 | 0.7 | - |
| Remove | removed | removed | removed | - |
| Constrain-Remove | 0.9→0.8 then remove | 0.8 then remove | removed | - |

---

## Meta Tag Categories

Tags from category 7 (Meta) are automatically detected based on image properties.

### Auto-Detected Tags

| Tag | Condition |
|-----|----------|
| `animated` | GIF with more than 1 frame |
| `thumbnail` | Both dimensions ≤ 250px |
| `low_res` | Both dimensions ≤ 500px |
| `hi_res` | Width ≥ 1600px OR height ≥ 1200px |
| `absurd_res` | Width ≥ 3200px OR height ≥ 2400px |
| `superabsurd_res` | Both dimensions ≥ 10000px |
| `4k` | 3840×2160, 2160×3840, 4096×2160, or 2160×4096 |
| `long_image` | Aspect ratio ≥ 4:1 or ≤ 1:4 |
| `tall_image` | Aspect ratio ≤ 1:4 (subset of long_image) |

### Aspect Ratio Tags

Standard aspect ratios are detected:

```
1:1, 2:1, 1:2, 3:1, 1:3, 3:2, 2:3,
4:3, 3:4, 5:3, 3:5, 5:4, 4:5,
6:5, 5:6, 7:4, 4:7, 7:3, 3:7,
16:10, 10:16, 11:8, 8:11, 14:9, 9:14,
16:9, 9:16, 21:9, 9:21
```

Additionally, `widescreen` is detected for 16:9 (1920x1080, 3840x2160) or 16:10 (1920x1200) aspect ratios:

### Implementation

```python
# app.py - detect_meta_tags_for_image_path
def detect_meta_tags_for_image_path(image_path):
    tags = set()
    with Image.open(image_path) as im:
        w, h = im.size
        
        # Animation detection
        if fmt == 'GIF':
            if im.n_frames > 1:
                tags.add('animated')
        
        # Resolution tags
        if w <= 250 and h <= 250:
            tags.add('thumbnail')
        if w <= 500 and h <= 500:
            tags.add('low_res')
        if w >= 1600 or h >= 1200:
            tags.add('hi_res')
        if w >= 3200 or h >= 2400:
            tags.add('absurd_res')
        if w >= 10000 and h >= 10000:
            tags.add('superabsurd_res')
        
        # 4K detection
        if (w == 3840 and h == 2160) or (w == 2160 and h == 3840) ...:
            tags.add('4k')
        
        # Aspect ratio
        ratio = w / h
        if ratio >= 4 or ratio <= 0.25:
            tags.add('long_image')
        
        # Specific ratios
        for tagname, a, b in ratios:
            if w * b == h * a:
                tags.add(tagname)
```

---

## Threshold System

### Threshold Presets

The frontend exposes three threshold presets:

| Preset | "All" Threshold | "Confident" Threshold |
|-------|----------------|---------------------|
| Conservative | 0.65 | 0.85 |
| Standard | 0.55 | 0.75 |
| Liberal | 0.45 | 0.65 |
| Custom | User-defined | User-defined |

### Threshold Semantics

- **All Threshold**: Tags with probability ≥ this value are considered "valid" 
- **Confident Threshold**: Tags with probability ≥ this value are considered "confident" and highlighted differently in UI

### Implementation

```python
# Frontend (script.js) threshold logic
const presets = {
    conservative: { all: 0.65, confident: 0.85 },
    standard: { all: 0.55, confident: 0.75 },
    liberal: { all: 0.45, confident: 0.65 }
};

// Applied in frontend for display:
// - Purple: prob >= confidentThreshold
// - Blue: prob >= allThreshold
// - Gray: prob < allThreshold
```

### Per-Tag Thresholds

For fine-tuning, use calibration files:

```csv
tag,threshold
female,0.55
anthro,0.50
furry,0.45
intersex,0.60
```

### CLI Usage

```bash
# Global threshold
python inference.py -t 0.2 image.png

# Per-tag calibration
python inference.py -t calibration.csv image.png
```

---

## Tag Output Format

### JSON Response

```json
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
    }
  ],
  "auto_meta": ["hi_res", "16:9"]
}
```

### e621 Format (Space-Separated)

```
female anthro solo furry blue_eyes smile
```

### PostyBirb Format (Comma-Separated)

```
female, anthro, solo, furry, blue_eyes, smile
```

### Tag Rewriting

Certain tags are rewritten for e621 compatibility (use `--original-tags` to disable):

| Original | Rewritten |
|----------|----------|
| `vulva` | `pussy` |

> **Note:** This tag rewriting only applies to CLI inference (`inference.py`). The Flask API (`/predict` endpoint) returns raw model tags without rewriting.

```bash
# Default: vulva → pussy
python inference.py image.png

# Keep original tags (for diffusion compatibility)
python inference.py --original-tags image.png
```

---

## Category Exclusion

Exclude specific categories from output:

```bash
# Exclude artist and lore tags
python inference.py -x artist -x lore image.png
```

### CLI Arguments

| Argument | Description |
|----------|-------------|
| `-t <float>` | Global threshold (-1.0 to 1.0 symmetric, or 0.0 to 1.0) |
| `-t <csv>` | Per-tag calibration file |
| `-i inherit` | Implication mode: inherit, constrain, remove, constrain-remove, off |
| `-x artist` | Exclude Artist category |
| `-x meta` | Exclude Meta category |
| `-x lore` | Exclude Lore category |
| `--original-tags` | Keep original tag names (disable vulva→pussy rewrite for diffusion) |

---

## Display Order

Tags are presented in e621 category order:

1. Copyright
2. Character
3. Species
4. Meta
5. General
6. Lore

Within each category, tags are sorted by probability (highest first).

---

## CSV Output Format

When using batch processing with CSV output:

```csv
filename,female,anthro,furry,solo,...
image1.png,0.95,0.89,0.87,...
image2.png,0.91,0.78,0.65,...
```

### With Per-Tag Probabilities

```bash
python inference.py -o - image.png

filename,female,anthro,furry
image.png,0.9500,0.8900,0.8700
```

---

## Frontend Tag Display

### Visual Categories

| Tag State | Background | Text | Condition |
|-----------|------------|------|-----------|
| Confident | #8b4aff (purple) | White | prob >= confidentThreshold |
| Valid | #3c6b8f (blue) | White | prob >= allThreshold |
| Low | #e0e5ec | #5a6b7c | prob < allThreshold |
| Added | #2e9a5c (green) | White | User manually added |
| Removed | #c53030 (red) | White | User manually removed |

### Tag Interaction

- **Click**: Toggle include/exclude (green/red)
- **Long press/Right-click**: Show e621 wiki description

### Category Header Colors

| Category | Color |
|----------|-------|
| Safe | #1f9d55 |
| Questionable | #d69e2e |
| Explicit | #c53030 |

These are rendered in the rating display based on tag presence.

---

## Metadata File Format

The tag metadata CSV files contain:

```csv
tag,category,implications
female,0,
male,0,
futanari,0,female male
intersex,0,female male
anthro,5,
```

### Fields

| Field | Description |
|-------|-------------|
| `tag` | Tag name |
| `category` | Category ID (0-8) |
| `implications` | Space-separated list of implied tags |

### Loading

```python
# inference.py
def load_metadata(path, rewrite_tag=lambda x: x):
    metadata = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            metadata[rewrite_tag(row["tag"])] = (
                int(row["category"]),
                [rewrite_tag(t) for t in row["implications"].split()]
            )
    return metadata
```

---

## Tag Count Limits

### Top-K Selection

The API returns a configurable number of tags:

| top_k | Description |
|-------|-------------|
| 50 | Minimal tags |
| 75 | Few tags |
| 100 | Standard |
| 150 | Extended |
| 200 | Default |
| 300 | Comprehensive |

### Implementation

```python
# app.py
DEFAULT_TOP_K = 200
ALLOWED_TOP_K = {50, 75, 100, 150, 200, 300}

# In predict route:
probs = torch.sigmoid(logits[0].float()).cpu()
values, indices = probs.topk(top_k)
```

---

## Rating Tags

e621 uses specific tags for content rating:

| Tag | Meaning |
|-----|---------|
| `safe` | Acceptable for all audiences |
| `questionable` | May be unsuitable for some |
| `explicit` | pornographic content |

These are detected from the model predictions, not auto-generated.

---

## Integration Points

### API Response Building

```python
# app.py
for idx, val in zip(indices, values):
    tag = tag_list[idx.item()]
    prob = val.item()
    cat_id = metadata.get(tag, (-1, []))[0]
    category_name = TAG_CATEGORIES.get(cat_id, "Other")
    tags_with_probs.append({
        "tag": tag,
        "prob": prob,
        "category": category_name
    })
```

### Frontend Rendering

See [JS.md](JS.md) for frontend display logic.

---

## CLI Examples

### Basic Tagging

```bash
python inference.py image.png
# Output: female anthro solo furry blue_eyes ...
```

### With Metadata

```bash
python inference.py -m data/jtp-3-hydra-tags.csv image.png
# Applies implications and categories
```

### Conservative Mode

```bash
python inference.py -t 0.4 -i inherit -x artist -x lore image.png
# Lower threshold, inherit implications, exclude artist/lore
```

### Batch Processing

```bash
python inference.py -r -o output.csv images/
# Process directory recursively, output CSV
```

### GPU Inference

```bash
python inference.py -d cuda image.png
# Use CUDA for faster processing
```