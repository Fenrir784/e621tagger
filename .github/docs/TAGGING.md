# Tag Classification and Implications

This document provides comprehensive documentation of the tag classification system used by e621tagger. It covers tag categories, subcategory classification, implication logic, threshold handling, and output presentation.

## Tag System Overview

e621tagger classifies images using **8,888 tags** (Hydra 3.5 model) organized into e621 categories. Tags are assigned confidence scores and can have implications (hierarchical relationships) that affect final output. Each `general`-category tag is further classified into one of **12 fine-grained subcategories** for better UI organization.

```
┌─────────────────────────────────────────────────────────────┐
│                 Tag Classification System                   │
│                                                             │
│  ┌─────────────────────────────────────────────────┐        │
│  │  Raw Model Output (8,888 logits)                │        │
│  └────────────────────────┬────────────────────────┘        │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────┐        │
│  │  Sigmoid Activation (0.0 - 1.0)                 │        │
│  └────────────────────────┬────────────────────────┘        │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────┐        │
│  │  Implication Application                        │        │
│  │  - Inherit, Constrain, Remove                   │        │
│  └────────────────────────┬────────────────────────┘        │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────┐        │
│  │  Threshold Filtering                            │        │
│  │  - Category exclusion                           │        │
│  │  - Per-tag thresholds                           │        │
│  └────────────────────────┬────────────────────────┘        │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────┐        │
│  │  Top-K Selection                                │        │
│  └────────────────────────┬────────────────────────┘        │
│                           │                                 │
│                           ▼                                 │
│  ┌──────────────────────────────────────────────────┐       │
│  │  Subcategory Classification                     │       │
│  │  - _SUBCATEGORY_MAP lookup                      │       │
│  │  - Color prefix heuristic fallback              │       │
│  └────────────────────────┬────────────────────────┘       │
│                           │                                 │
│                           ▼                                 │
│  ┌──────────────────────────────────────────────────┐       │
│  │  Category + Meta Tag Assignment                  │       │
│  └──────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## Tag Categories

Tags are organized into e621 categories with numeric IDs:

### Category Mapping

| Category ID | Name | Description | Example Tags |
|-------------|------|-------------|--------------|
| 0 | General | General subject matter (includes 100-111) | `female`, `male`, `anthro`, `solo` |
| 1 | Artist | Artist names | `artist:fenrir784`, `oc:request` |
| 2 | Contributor | Contributor tags | (rarely used) |
| 3 | Copyright | Series/franchise | `sonic_the_hedgehog`, `nintendo` |
| 4 | Character | Fictional characters | `miles_tails_prower` |
| 5 | Species | Species/body types | `wolf`, `dragon`, `fox` |
| 6 | Invalid | Invalid tags | (rarely used) |
| 7 | Meta | Rating and technical | `safe`, `questionable`, `hi_res` |
| 8 | Lore | Story elements | `backstory`, `backview` |
| 100 | Accessories, Items, Clothing | Clothing and items | `scarf`, `hat`, `belt` |
| 101 | Actions, Positions, State | Actions and poses | `sitting`, `walking`, `sleeping` |
| 102 | Body Color | Color markings | `red_fur`, `blue_eyes`, `black_markings` |
| 103 | Body Features | Body parts/features | `tail`, `wings`, `horns` |
| 104 | Effects, Fluids | Visual effects | `cum`, `sparkles`, `glowing` |
| 105 | Fetishes, Specifics, Interactions | Adult content | `anal`, `footjob`, `bondage` |
| 106 | Genders, Demographics | Gender-related | `male`, `female`, `herm`, `femboy` |
| 107 | Locations, Backgrounds, Setting | Environments | `forest`, `bedroom`, `beach` |
| 108 | Poses, Scenarios, Situations | Scene setup | `profile_view`, `closeup`, `action_pose` |
| 109 | Style, Perspective | Art style | `chibi`, `realistic`, `comic` |
| 110 | Text, Symbols, UI, Vocalization | Text elements | `speech_bubble`, `sound_effect`, `onomatopoeia` |
| 111 | Other | Miscellaneous | Tags from unrecognized categories |

> **Note:** When copying tags to clipboard, categories 100-111 are merged into "General" to maintain e621 compatibility. The web interface displays all 21 categories separately for better visual organization.

### From Code

```python
# app.py
TAG_CATEGORIES = {
    0: "General",
    1: "Artist",
    2: "Contributor",
    3: "Copyright",
    4: "Character",
    5: "Species",
    6: "Invalid",
    7: "Meta",
    8: "Lore",
    100: "Accessories, Items, Clothing",
    101: "Actions, Positions, State",
    102: "Body Color",
    103: "Body Features",
    104: "Effects, Fluids",
    105: "Fetishes, Specifics, Interactions",
    106: "Genders, Demographics",
    107: "Locations, Backgrounds, Setting",
    108: "Poses, Scenarios, Situations",
    109: "Style, Perspective",
    110: "Text, Symbols, UI, Vocalization",
    111: "Other",
}
```

---

## Subcategory Classification

General tags (category 0) are further split into **12 fine-grained subcategories** for better UI organization. The subcategory is determined by `Label.subcategory` in `hydra/label.py`.

### Subcategory Mapping

| Subcategory | Code | Description | Examples |
|-------------|------|-------------|----------|
| Accessories, Items, Clothing | `accessory` | Clothing, accessories, items | `scarf`, `hat`, `belt`, `sword` |
| Actions, Positions, State | `action` | Actions and dynamic states | `kissing`, `running`, `sitting_on_lap` |
| Body Color | `color` | Color markings | `red_fur`, `blue_eyes`, `black_markings` |
| Body Features | `body_feature` | Body parts/features | `tail`, `wings`, `horns`, `claws` |
| Effects, Fluids | `effect` | Visual effects, fluids | `sparkles`, `glowing`, `cum` |
| Fetishes, Specifics, Interactions | `fetish` | Adult content categories | `anal`, `footjob`, `bondage` |
| Genders, Demographics | `demographic` | Gender-related | `male`, `female`, `herm`, `femboy` |
| Locations, Backgrounds, Setting | `setting` | Environments | `forest`, `bedroom`, `beach` |
| Poses, Scenarios, Situations | `pose` | Scene setup | `profile_view`, `closeup`, `splits` |
| Style, Perspective | `style` | Art style | `chibi`, `realistic`, `comic`, `perspective` |
| Text, Symbols, UI, Vocalization | `text` | Text elements | `speech_bubble`, `onomatopoeia` |
| Other | `other` | Miscellaneous | Unrecognized / uncategorized tags |

### Implementation

**File**: `hydra/_subcat.py`

The subcategory is resolved via `Label.subcategory` in `hydra/label.py:102-121`:

```python
@property
@cache
def subcategory(self) -> str | None:
    if self.category == "general":
        if self.label in _SUBCATEGORY_MAP:
            return _SUBCATEGORY_MAP[self.label]
        if (
            self.label.startswith(COLOR_PREFIXES)
            and not self.label.endswith(COLOR_EXCEPTIONS)
        ):
            return "color"
        return None

    if (
        self.category == "meta"
        and self.label in ("safe", "questionable", "explicit")
    ):
        return "rating"

    return None
```

### Mapping Strategy

The `_SUBCATEGORY_MAP` in `hydra/_subcat.py` is a pre-built dictionary of **6,263 tag→subcategory** mappings. At inference time, the subcategory is resolved by [`Label.subcategory`](#implementation) via:

1. **Direct lookup** in `_SUBCATEGORY_MAP` (covers the majority of general tags)
2. **Color prefix heuristic** in `label.py` — tags starting with color prefixes (e.g. `red_`, `blue_`, `black_`) that aren't in the map but aren't color exceptions are classified as `"color"`
3. **Fallback** — `None` for tags that don't match either

| Lookup | Description | Tags Covered |
|--------|-------------|--------------|
| 1. `_SUBCATEGORY_MAP` | Pre-built dictionary mapping each known general tag to its subcategory | 6,263 |
| 2. Color prefix | `COLOR_PREFIXES` in `label.py` (18+ prefixes like `red_`, `blue_`, `dark_`) | Remaining color tags |
| 3. Fallback | Returns `None` | Unclassified tags |

### Coverage Validation

The subcategory mapping was validated by 12 independent sub-agents, each reviewing every general tag in their domain (6,263 total). The validation process identified **1,951 corrections** across all 12 subcategories:

| Subcategory | Corrections Applied |
|-------------|--------------------|
| action | 527 |
| accessory | 283 |
| pose | 227 |
| body_feature | 219 |
| other | 202 |
| effect | 123 |
| demographic | 92 |
| style | 88 |
| color | 73 |
| text | 58 |
| setting | 33 |
| fetish | 26 |
| **Total** | **1,951** |

### Subcategory in the API

The `/predict` endpoint returns subcategory via the `category` field:

```json
{
  "tag": "female",
  "prob": 0.95,
  "category": "Genders, Demographics"
}
```

The `SUBCATEGORY_DISPLAY_NAMES` map in `app.py:32-45` converts internal subcategory codes to display names.

### Web UI Display

The frontend in `script.js` uses `displayCategoryOrder` (line 36) to render all 12 subcategories as separate visual categories, each with its own color-coded header. When copying to clipboard, subcategories are merged back into "General" for e621 compatibility.

---

## Implication System

Tags can imply other tags in hierarchical relationships. For example:
- `sunglasses_on_head` implies `eyewear_on_head` and `sunglasses`
- `vibrator` implies `sex_toy` (in some contexts)
- `water_bottle` implies `bottle`

### Implication Modes

The pipeline supports several modes for handling implications, configured via the `implications` parameter in `classification.py`:

| Mode | Description | Behavior |
|------|-------------|----------|
| `off` | No implications | Simple threshold filtering only |
| `preserve` | Qualify implications | Require implied tags to meet threshold |
| `inherit` | Tags inherit highest probability | If A implies B, B's prob = max(B's prob, A's prob) |
| `constrain` | Tags constrained to lowest | If A implies B, A's prob = min(A's prob, B's prob) |
| `remove` | Exclude implied tags | Remove all tags implied by other tags |
| `constrain-remove` | Combination | Constrain then remove |
| `enforce` | Enforce implications | Remove tags whose implied tags don't meet threshold |
| `enforce-inherit` | Enforce + inherit | Enforce then inherit |
| `enforce-constrain` | Enforce + constrain | Enforce then constrain |
| `enforce-remove` | Enforce + remove | Enforce then remove |

### Implementation

```python
def _inherit_implications(
    outputs: dict[str, float],
    antecedent: str, prob: float,
    labels: dict[str, tuple[Label, float]]
) -> None:
    if (label := labels.get(antecedent)) is None:
        return

    for consequent in label[0].implies:
        if outputs.get(consequent, float("+inf")) < prob:
            outputs[consequent] = prob

        _inherit_implications(outputs, consequent, prob, labels)

def _constrain_implications(
    outputs: dict[str, float],
    consequent: str, prob: float,
    labels: dict[str, tuple[Label, float]]
) -> None:
    if (label := labels.get(consequent)) is None:
        return

    for antecedent in label[0].implied_by:
        if outputs.get(antecedent, float("-inf")) > prob:
            outputs[antecedent] = prob

        _constrain_implications(outputs, antecedent, prob, labels)

def _remove_consequents(
    outputs: dict[str, float], antecedent: str,
    labels: dict[str, tuple[Label, float]]
) -> None:
    if (label := labels.get(antecedent)) is None:
        return

    for consequent in label[0].implies:
        outputs.pop(consequent, None)
        _remove_consequents(outputs, consequent, labels)
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

Additionally, `widescreen` is detected for 16:9 or 16:10 aspect ratios:

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
| Conservative | 0.70 | 0.80 |
| Standard | 0.60 | 0.70 |
| Liberal | 0.50 | 0.60 |
| Custom | User-defined | User-defined |

### Threshold Semantics

- **All Threshold**: Tags with probability ≥ this value are considered "valid" 
- **Confident Threshold**: Tags with probability ≥ this value are considered "confident" and highlighted differently in UI

### Implementation

```python
# Frontend (script.js) threshold logic
const presets = {
    conservative: { all: 0.70, confident: 0.80 },
    standard: { all: 0.60, confident: 0.70 },
    liberal: { all: 0.50, confident: 0.60 }
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

> **Note:** The Flask API (`/predict` endpoint) returns raw model tags without rewriting.


| `-x lore` | Exclude Lore category |
| `--original-tags` | Keep original tag names (disable vulva→pussy rewrite for diffusion) |

---

## Display Order

There are two category orderings:

### Copy Action (e621 format)
Tags are presented in e621 category order when copying to clipboard. Categories 100-111 (fine-grained General sub-categories) are merged into General:

1. Copyright
2. Character
3. Species
4. Meta
5. General (includes tags from IDs 100-111)
6. Lore

### Site Display (Web UI)
The web interface displays all 21 categories separately for better visual organization. Body Color and Lore are placed at the bottom:

1. General
2. Artist
3. Contributor
4. Copyright
5. Character
6. Species
7. Invalid
8. Meta
9. Accessories, Items, Clothing
10. Actions, Positions, State
11. Body Features
12. Effects, Fluids
13. Fetishes, Specifics, Interactions
14. Genders, Demographics
15. Locations, Backgrounds, Setting
16. Poses, Scenarios, Situations
17. Style, Perspective
18. Text, Symbols, UI, Vocalization
19. Other
20. Body Color
21. Lore

Within each category, tags are sorted by probability (highest first).

---

## CSV Output Format

When using batch processing with CSV output:

```csv
filename,female,anthro,furry,solo,...
image1.png,0.95,0.89,0.87,...
image2.png,0.91,0.78,0.65,...
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
| `category` | Category ID (0-8, 100-111) |
| `implications` | Space-separated list of implied tags |



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
# app.py:462-474
for idx, val in zip(indices, values):
    label = model.labels[int(idx.item())]
    prob = val.item()
    if label.subcategory and label.subcategory in SUBCATEGORY_DISPLAY_NAMES:
        category_name = SUBCATEGORY_DISPLAY_NAMES[label.subcategory]
    else:
        category_name = TAG_CATEGORIES.get(label.category, label.category.title())
    tags_with_probs.append({
        "tag": label.label,
        "prob": prob,
        "category": category_name
    })
```

### Frontend Rendering

See [JS.md](JS.md) for frontend display logic.

---

## Category Hiding/Exclusion

Users can hide entire tag categories (e.g., Fetishes, Body Color) to reduce visual clutter and exclude them from copy output.

### UI Interaction

Each `.category-block` renders a faint ✕ toggle button in the top-right of its header area:

| Action | Control | Effect |
|--------|---------|--------|
| **Hide** | Click ✕ | Gray out category (opacity 0.35), disable tag interaction, exclude from copy |
| **Show** | Click ✓ (formerly ✕) | Restore full opacity, re-enable interaction, include in copy |
| **Persist** | Click "Always hide" text (appears when hidden) | Save preference to localStorage, survives page reload |
| **Unpersist** | Click "Always hide" again | Remove localStorage preference |

### Behavior

- **Hidden categories**: The `.category-block` gets `.category-hidden` class → opacity 0.35. All `.tag` children get `pointer-events: none`, making them non-interactive.
- **Copy exclusion**: Hidden categories are filtered out in `filterTags()` before clipboard copy.
- **Per-upload reset**: `hiddenCategories` (session-only) is cleared on each new upload. `alwaysHiddenCategories` (persistent) is re-applied from localStorage.
- **Manual tag corrections** (`addedTags`/`removedTags`) are preserved across hide/unhide operations.
- **Always-hidden reordering**: Categories in `alwaysHiddenCategories` are sorted to the end of the display, keeping them out of the way. Removing the "always hide" preference restores their original position.

### State Management

| Variable | Type | Scope | Persistence |
|----------|------|-------|-------------|
| `hiddenCategories` | `Set` | Session (per upload) | Not persisted |
| `alwaysHiddenCategories` | `Set` | Global | localStorage via `e621tagger-settings` |

### localStorage

Stored as `alwaysHiddenCategories` array inside the `e621tagger-settings` JSON object:

```json
{
  "alwaysHiddenCategories": ["Fetishes, Specifics, Interactions", "Body Color"],
  "allThreshold": 0.60,
  ...
}
```

### Reset

The **Reset** button in settings clears both `alwaysHiddenCategories` and removes it from `localStorage`.