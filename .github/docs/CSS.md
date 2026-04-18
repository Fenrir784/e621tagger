# Frontend CSS Documentation

This document provides comprehensive documentation of the e621tagger frontend styles. It covers CSS custom properties, themes, components, animations, and responsive design.

---

## File Overview

**Location**: `static/css/style.css`

**Size**: ~872 lines

**Purpose**: All styling for the e621tagger web interface

---

## CSS Custom Properties

### Root Variables

```css
:root {
    --bg-color: #f5f7fa;
    --text-color: #2d3748;
    --primary-color: #6b4aff;
    --secondary-color: #eef2f6;
    --border-color: #e2e8f0;
    --success-color: #2e9a5c;
    --confident-bg: #8b4aff;
    --confident-text: #fff;
    --all-bg: #3c6b8f;
    --all-text: #fff;
    --low-bg: #e0e5ec;
    --low-text: #5a6b7c;
    --error-bg: #fef2f2;
    --error-text: #b91c1c;
    --error-border: #fecaca;
    --safe-bg: #1f9d55;
    --questionable-bg: #d69e2e;
    --explicit-bg: #c53030;
    --disabled-bg: #cbd5e1;
    --disabled-text: #f7fafc;
    --menu-bg: var(--secondary-color);
    --added-bg: #2e9a5c;
    --added-text: #fff;
    --removed-bg: #c53030;
    --removed-text: #fff;
    --success-bg: #2e9a5c;
    --success-border: #1e7e34;
    --glow-color: rgba(139, 92, 246, 0.1);
    --glow-strong: rgba(139, 92, 246, 0.2);
    --glow-stronger: rgba(139, 92, 246, 0.5);
    --box-shadow-light: rgba(0, 0, 0, 0.1);
    --box-shadow-medium: rgba(0, 0, 0, 0.15);
    --box-shadow-heavy: rgba(0, 0, 0, 0.2);
    --box-shadow-heavyplus: rgba(0, 0, 0, 0.3);
    --overlay-bg: rgba(0, 0, 0, 0.5);
    --animation-duration: 0.3s;
}
```

### Color Variables

| Variable | Light Mode | Dark Mode | Usage |
|----------|-----------|----------|-------|
| `--bg-color` | #f5f7fa | #0a0c10 | Page background |
| `--text-color` | #2d3748 | #e5e7eb | Text color |
| `--primary-color` | #6b4aff | #8b5cf6 | Accent color |
| `--secondary-color` | #eef2f6 | #1f2937 | Secondary bg |
| `--border-color` | #e2e8f0 | #374151 | Borders |

### Tag State Colors

| Variable | Color | State |
|----------|-------|-------|
| `--confident-bg` | #8b4aff | High confidence |
| `--all-bg` | #3c6b8f | Medium confidence |
| `--low-bg` | #e0e5ec | Low confidence |
| `--added-bg` | #2e9a5c | User added |
| `--removed-bg` | #c53030 | User removed |

### Rating Colors

| Variable | Color | Rating |
|----------|-------|--------|
| `--safe-bg` | #1f9d55 | Safe |
| `--questionable-bg` | #d69e2e | Questionable |
| `--explicit-bg` | #c53030 | Explicit |

### Shadow Variables

| Variable | Usage |
|----------|-------|
| `--box-shadow-light` | Subtle shadows |
| `--box-shadow-medium` | Elevated elements |
| `--box-shadow-heavy` | Dropdowns |
| `--box-shadow-heavyplus` | Modals |

---

## Theme System

### Auto Dark Theme (via OS preference)

```css
@media (prefers-color-scheme: dark) {
    :root:not(.theme-light):not(.theme-dark) {
        --bg-color: #0a0c10;
        --text-color: #e5e7eb;
        --primary-color: #8b5cf6;
        --secondary-color: #1f2937;
        --border-color: #374151;
        ...
    }
}
```

### Theme Dark Class

```css
.theme-dark {
    --bg-color: #0a0c10;
    --text-color: #e5e7eb;
    --primary-color: #8b5cf6;
    --secondary-color: #1f2937;
    --border-color: #374151;
    ...
}
```

### Theme Light Class

```css
.theme-light {
    --bg-color: #ebebeb;
    --text-color: #1c222d;
    --primary-color: #6b4aff;
    --secondary-color: #eef2f6;
    --border-color: #4f4f4f40;
    /* Different from root defaults: */
    --confident-bg: #5f1ed3;  /* Slightly darker purple than root #8b4aff */
    --all-bg: #3c6b8f;
    --low-bg: #cfcfcf;       /* Darker gray than root #e0e5ec */
    ...
}
```

**Note:** `.theme-light` class overrides specific colors to ensure readability:
| Variable | Root | .theme-light | Why |
|----------|------|-------------|------|
| `--confident-bg` | #8b4aff | #5f1ed3 | Better contrast on light bg |
| `--low-bg` | #e0e5ec | #cfcfcf | Better contrast |

### Theme Toggle Buttons

```html
<div class="theme-toggle-group" id="themeToggle">
    <button type="button" class="theme-option active" data-value="system">💻</button>
    <button type="button" class="theme-option" data-value="light">☀️</button>
    <button type="button" class="theme-option" data-value="dark">🌙</button>
</div>
```

### Auto Theme Detection

The system automatically detects OS preference via `prefers-color-scheme: dark` media query when no explicit theme class is applied.

---

## Global Reset

The CSS reset is split into four separate blocks for proper base styling.

### Base Reset

```css
*, body { margin: 0; padding: 0; box-sizing: border-box; }
```

### HTML Reset

```css
html { position: relative; overflow-x: hidden; height: 100%; }
```

### Body Reset

```css
body { position: relative; overflow-x: hidden; width: 100%; }
button { outline: none; }
```

### Body Element Styles

```css
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: var(--bg-color);
    color: var(--text-color);
    line-height: 1.6;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    justify-content: flex-start;
    transition: filter 0.6s, opacity 0.6s;
    user-select: none;
    -webkit-tap-highlight-color: transparent;
}
body.modal-open { overflow: hidden; }
```

---

## Layout Container

### Container

```css
.container {
    max-width: 800px;
    width: 90%;
    margin: 2rem auto 0;
    padding: 2rem;
    position: relative;
}
```

### Header

```css
header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 2rem;
    gap: 1rem;
}
.header-left, .header-right { flex: 1; display: flex; }
.header-left { justify-content: flex-start; }
.header-right { justify-content: flex-end; }
```

### Page Title

```css
h1 {
    font-size: 2.5rem;
    font-weight: 300;
    color: var(--confident-bg);
    line-height: 1.2;
}
```

---

## Settings Toggle Button

```css
.settings-toggle {
    background: var(--secondary-color);
    border: none;
    font-size: 1.8rem;
    cursor: pointer;
    padding: 0.5rem;
    border-radius: 50%;
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-color);
    transition: all 0.2s;
    box-shadow: 0 2px 8px var(--box-shadow-light);
    touch-action: manipulation;
}
.settings-toggle:active, .settings-toggle.pressed { transform: scale(0.95); filter: brightness(0.95); }
.settings-toggle.open { transform: scale(1.1); }
```

---

## Easter Egg Container

Animated easter egg feature with three layers that animate on open.

```css
.egg-container {
    width: 80px;
    height: 80px;
    position: relative;
    cursor: pointer;
    transition: transform 0.2s;
}
.egg-container:active { transform: scale(0.95); }
.egg-top, .egg-bottom, .egg-creature {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.2s;
    image-rendering: crisp-edges;
    object-fit: contain;
}
.egg-top { transform: translateY(0); z-index: 3; }
.egg-bottom { transform: translateY(0); z-index: 2; }
.egg-creature { opacity: 0; transform: scale(0.8); z-index: 1; }
.egg-container.open .egg-top { transform: translateY(-16px); }
.egg-container.open .egg-bottom { transform: translateY(16px); }
.egg-container.open .egg-creature { opacity: 1; transform: scale(1); z-index: 4; }
```

---

## Settings Menu

### Menu Structure

```css
.settings-menu {
    position: absolute;
    width: 300px;
    background-color: var(--menu-bg);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    box-shadow: 0 8px 24px var(--box-shadow-heavy);
    padding: 1rem;
    z-index: 100;
    opacity: 0;
    transform: translateY(-10px);
    visibility: hidden;
    transition: opacity 0.2s, transform 0.2s, visibility 0.2s;
}
.settings-menu.show { opacity: 1; transform: translateY(0); visibility: visible; }
```

### Settings Header

```css
.settings-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    font-weight: 600;
    color: var(--confident-bg);
    position: relative;
}
```

### Close Button

```css
.close-settings {
    background: none;
    border: none;
    font-size: 1.2rem;
    cursor: pointer;
    color: var(--text-color);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
}
```

---

## Settings Sections

```css
.settings-section {
    margin-bottom: 1.2rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--border-color);
}
.settings-section:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
.settings-section h2 {
    font-size: 0.9rem;
    margin-bottom: 0.8rem;
    color: var(--confident-bg);
    opacity: 0.9;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.settings-section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.8rem;
}
```

---

## Help Button

```css
.help-btn {
    background: none;
    border: none;
    font-size: 0.8rem;
    color: var(--confident-bg);
    text-decoration: underline dotted;
    cursor: pointer;
    padding: 0.2rem 0.4rem;
    border-radius: 4px;
}
```

---

## Toggle Group Components

### Theme Toggle Group

```css
.theme-toggle-group, .format-toggle-group, .max-tags-group {
    display: flex;
    gap: 0.2rem;
    background-color: var(--bg-color);
    padding: 0.15rem;
    border-radius: 30px;
}
.theme-toggle-group { margin-left: 0.5rem; }
.max-tags-group { width: 100%; padding: 0.2rem; }
.format-toggle-group { padding: 0.2rem; gap: 0.1rem; }
```

### Toggle Options

```css
.theme-option, .format-option, .max-tag-option {
    border: none;
    background: none;
    padding: 0.2rem 0.4rem;
    border-radius: 20px;
    cursor: pointer;
    font-size: 0.8rem;
    color: var(--text-color);
    transition: filter 0.2s, background-color 0.2s, color 0.2s, transform 0.15s;
    border: 1px solid transparent;
    touch-action: manipulation;
}
.format-option, .max-tag-option { padding: 0.4rem 0; flex: 1; text-align: center; font-weight: 500; border-radius: 30px; }

/* Note: .tag.confident below is for preset buttons, NOT tag elements.
   Tag elements use data-level attribute (see Tag States section). */
.theme-option.active, .format-option.active, .max-tag-option.active, .preset-btn.active, .tag.confident {
    background-color: var(--confident-bg);
    color: var(--confident-text);
    border-color: var(--confident-bg);
    filter: brightness(1.1);
}
```

### Format Toggle

Controls output format: **e621** (danbooru-style) or **PostyBirb** (comma-separated).

```css
.format-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-left: auto;
}
.toggle-label {
    font-size: 0.8rem;
    color: var(--text-color);
    opacity: 0.7;
}
.format-toggle-group { width: fit-content; min-width: 140px; }
.format-toggle-group .format-option { font-size: 0.85rem; }

#defaultFormatToggle {
    width: 100%;
}
```

> **Note:** The format toggle uses `'e621'` as the internal value for danbooru format. Any other value (including the default) uses PostyBirb format.

### Max Tags Group

Controls maximum tags to display

```css
.max-tags-group { width: 100%; padding: 0.2rem; }
```

---

## Preset Buttons

### Preset Structure

```css
.preset-buttons {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
}
.preset-btn {
    background-color: var(--bg-color);
    border: 1px solid var(--border-color);
    color: var(--text-color);
    padding: 0.5rem 0.8rem;
    border-radius: 30px;
    cursor: pointer;
    font-size: 0.9rem;
    text-align: center;
    transition: filter 0.2s, transform 0.15s;
}
.preset-btn.active {
    background-color: var(--confident-bg);
    color: var(--confident-text);
    border-color: var(--confident-bg);
}
```

---

## Custom Thresholds Panel

### Panel Structure

```css
.custom-thresholds-panel {
    overflow: hidden;
    transition: max-height 0.3s;
    max-height: 0;
}
.custom-thresholds-panel.open { max-height: 150px; margin-top: 0.8rem; }
```

### Custom Inputs

```css
.custom-inputs {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.8rem;
}
.input-group {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
}
.input-group label { font-size: 0.7rem; opacity: 0.7; }
.input-group input {
    background-color: var(--bg-color);
    border: 1px solid var(--border-color);
    color: var(--text-color);
    padding: 0.4rem;
    border-radius: 6px;
    font-size: 0.8rem;
}
```

### Action Buttons

```css
.apply-btn {
    background-color: var(--confident-bg);
    color: var(--confident-text);
    border: none;
    padding: 0.4rem 1rem;
    border-radius: 20px;
    cursor: pointer;
    font-size: 0.8rem;
    width: 100%;
    transition: transform 0.15s, opacity 0.15s;
}
.reset-btn {
    background: none;
    border: 1px solid var(--border-color);
    color: var(--text-color);
    padding: 0.5rem 1rem;
    border-radius: 30px;
    cursor: pointer;
    font-size: 0.9rem;
    width: 100%;
    transition: filter 0.2s, transform 0.15s, opacity 0.15s;
}
.reset-btn:active {
    background-color: var(--error-bg);
    color: var(--error-text);
    border-color: var(--error-border);
    filter: brightness(0.85);
}
```

---

## Button Active States

All buttons have active/press states that scale down slightly and reduce opacity:

```css
.preset-btn:active, .apply-btn:active, .reset-btn:active, .global-copy-btn:active, .close-settings:active {
    transform: scale(0.98);
    opacity: 0.9;
}
.theme-option:active, .format-option:active, .max-tag-option:active {
    transform: scale(0.95);
    opacity: 0.9;
}
```

---

## Hover Interactions

Critical hover interactions defined in `@media (hover: hover)` block:

```css
@media (hover: hover) {
    /* Settings toggle */
    .settings-toggle:hover { transform: scale(1.1); }

    /* Help button */
    .help-btn:hover { filter: brightness(0.95); }

    /* Preset buttons */
    .preset-btn:hover { filter: brightness(1.15); }

    /* Global copy buttons */
    .global-copy-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px var(--box-shadow-heavy);
        filter: brightness(1.1);
    }

    /* Category copy buttons */
    .cat-copy-btn:hover:not(:disabled) { transform: scale(1.1); opacity: 0.9; }

    /* Close popup buttons */
    .close-popup:hover { filter: brightness(0.9); }

    /* Links */
    .site-info a:hover { text-decoration: underline; }
    .tag-popup-text a:hover { text-decoration: underline; }
    .help-footer a:hover { text-decoration: underline; }

    /* Drop zone */
    #dropZone:hover {
        border-color: var(--confident-bg);
        background-color: rgba(139, 92, 246, 0.1);
    }
}
```

**Note:** These hover states only apply on devices with hover capability (not touch devices).

---

## Notification Container

### Container Structure

```css
#notification-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 1000;
    display: flex;
    flex-direction: column;
    gap: 10px;
    pointer-events: none;
}
```

### Notification Types

```css
.notification {
    max-width: 300px;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    box-shadow: 0 4px 12px var(--box-shadow-medium);
    font-weight: 500;
    opacity: 0;
    transform: translateX(20px);
    animation: slideIn 0.3s forwards;
    pointer-events: auto;
}
.notification.error {
    background-color: var(--error-bg);
    color: var(--error-text);
    border: 1px solid var(--error-border);
}
.notification.success {
    background-color: var(--success-bg);
    color: white;
    border: 1px solid var(--success-border);
}
.notification.info {
    background-color: var(--primary-color);
    color: var(--confident-text);
    border: 1px solid var(--confident-bg);
}
```

### Toast Types

| Type | Background | Border |
|------|-------------|--------|
| Error | var(--error-bg) | var(--error-border) |
| Success | var(--success-bg) | var(--success-border) |
| Info | var(--primary-color) | var(--confident-bg) |

### Slide In Animation

```css
@keyframes slideIn {
    0% { opacity: 0; transform: translateX(20px); }
    100% { opacity: 1; transform: translateX(0); }
}
```

---

## Drop Zone

### Drop Zone Structure

```css
#dropZone {
    border: 2px dashed var(--border-color);
    border-radius: 12px;
    padding: 3rem 2rem;
    text-align: center;
    cursor: pointer;
    transition: transform var(--animation-duration), filter var(--animation-duration), box-shadow 0.3s, border-color 0.3s, background-color 0.3s;
    margin-bottom: 2rem;
    min-height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background-color: var(--secondary-color);
    touch-action: manipulation;
}
#dropZone.dragover {
    filter: brightness(1.1);
    transform: scale(1.02);
}
#dropZone.has-image { padding: 0; border-style: solid; }
#dropZone.uploading { animation: pulseGlow 1.5s infinite; }
```

### Upload States

| State | Style |
|-------|-------|
| Default | Dashed border, secondary-color bg |
| Dragover | Brighter, scaled 1.02 |
| Has Image | Solid border, padding removed |
| Uploading | Animated pulse glow |

### Upload Image

```css
#dropZone img {
    max-width: 100%;
    max-height: 300px;
    object-fit: contain;
    border-radius: 8px;
    display: block;
    animation: fadeInScale 0.2s;
}
```

### Upload Content

```css
.upload-content {
    display: flex;
    flex-direction: column;
    align-items: center;
}
.upload-icon { stroke: var(--text-color); margin-bottom: 1rem; }
.small { font-size: 0.875rem; color: var(--low-text); margin-top: 0.5rem; }
```

### Pulse Glow Animation

```css
@keyframes pulseGlow {
    0% { box-shadow: 0 0 0 0 var(--glow-strong); }
    50% { box-shadow: 0 0 30px 10px var(--glow-stronger); }
    100% { box-shadow: 0 0 0 0 var(--glow-strong); }
}
```

---

## Results Display

### Results Container

```css
.results {
    background-color: var(--secondary-color);
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 4px 20px var(--box-shadow-heavyplus);
    min-height: 200px;
    position: relative;
    transition: opacity 0.3s, transform 0.3s;
    opacity: 0;
    transform: scale(0.95);
}
.results.visible { opacity: 1; transform: scale(1); }
.results-content { transition: opacity 0.2s; }
.results.loading .results-content { opacity: 0.3; pointer-events: none; }
```

### Results Header

```css
.results-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
    gap: 1rem;
}
.results-header h2 { font-weight: 400; color: var(--confident-bg); flex-shrink: 0; }
.format-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-left: auto;
}
```

### Global Copy Buttons

```css
.global-buttons {
    display: flex;
    gap: 1.5rem;
    margin-bottom: 1.5rem;
    justify-content: center;
}
.global-copy-btn {
    border: none;
    padding: 0.8rem 1.2rem;
    border-radius: 40px;
    cursor: pointer;
    font-size: 1rem;
    font-weight: 600;
    letter-spacing: 0.3px;
    box-shadow: 0 4px 12px var(--box-shadow-medium);
    width: 240px;
    text-align: center;
    transition: filter 0.2s, box-shadow 0.2s, transform 0.15s;
    white-space: nowrap;
    touch-action: manipulation;
}
.global-copy-btn.confident { background-color: var(--confident-bg); color: var(--confident-text); }
.global-copy-btn.all { background-color: var(--all-bg); color: var(--all-text); }
.global-copy-btn.copied { background-color: var(--success-color); }
```

---

## Rating Display

### Rating Container

```css
.rating-container {
    display: flex;
    justify-content: flex-start;
    margin-bottom: 1rem;
}
.rating-display {
    font-size: 0.85rem;
    padding: 0.2rem 1rem;
    border-radius: 30px;
    font-weight: 500;
    letter-spacing: 0.3px;
    display: inline-block;
    color: #fff;
}
.rating-display.safe { background-color: var(--safe-bg); }
.rating-display.questionable { background-color: var(--questionable-bg); }
.rating-display.explicit { background-color: var(--explicit-bg); }
```

### Rating Badges

| Class | Background | Rating |
|-------|-------------|--------|
| `.safe` | var(--safe-bg) | Safe |
| `.questionable` | var(--questionable-bg) | Questionable |
| `.explicit` | var(--explicit-bg) | Explicit |

---

## Categories

### Categories Container

```css
.categories-container { display: flex; flex-direction: column; gap: 1rem; }
.category-block {
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 0.5rem;
    background-color: var(--bg-color);
}
```

### Category Header

```css
.category-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
    padding-bottom: 0.3rem;
    border-bottom: 1px solid var(--border-color);
}
.category-name {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--confident-bg);
    text-transform: uppercase;
}
.category-buttons { display: flex; gap: 0.3rem; }
```

### Category Copy Button

```css
.cat-copy-btn {
    border: none;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: opacity 0.2s, transform 0.15s, filter 0.2s;
    box-shadow: 0 2px 6px var(--box-shadow-medium);
    touch-action: manipulation;
}
.cat-copy-btn.confident { background-color: var(--confident-bg); color: var(--confident-text); }
.cat-copy-btn.all { background-color: var(--all-bg); color: var(--all-text); }
.cat-copy-btn:disabled {
    background-color: var(--disabled-bg);
    color: var(--disabled-text);
    cursor: not-allowed;
    opacity: 0.5;
    box-shadow: none;
    pointer-events: none;
}
.cat-copy-btn.copied { background-color: var(--success-color); transform: scale(0.95); }
```

---

## Tags

### Tag Styles

**IMPORTANT:** Tags use `data-level` attribute for styling, not CSS classes directly.

```css
.category-tags { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.tag {
    background-color: var(--low-bg);
    color: var(--low-text);
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    font-size: 0.8rem;
    border: 1px solid transparent;
    opacity: 0.6;
    animation: fadeInScale 0.2s;
    cursor: pointer;
    line-height: 1.2;
    touch-action: manipulation;
    transition: background-color 0.2s, color 0.2s, opacity 0.2s, transform 0.1s;
}
.tag:active { transform: scale(0.97); }
```

### Tag States (via data-level attribute)

| Data Level | Background | Text | Font Weight |
|------------|------------|------|-------------|
| `all` | var(--all-bg) | var(--all-text) | 400 |
| `confident` | var(--confident-bg) | var(--confident-text) | 600 |
| `added` | var(--added-bg) | var(--added-text) | border success |
| `removed` | var(--removed-bg) | var(--removed-text) | strikethrough, 400 |

**Key Implementation Detail:**
```css
.tag[data-level="all"] { background-color: var(--all-bg); color: var(--all-text); font-weight: 400; }
.tag[data-level="confident"] { background-color: var(--confident-bg); color: var(--confident-text); font-weight: 600; }
.tag[data-level="added"] { background-color: var(--added-bg); color: var(--added-text); border-color: var(--success-color); }
.tag[data-level="removed"] { background-color: var(--removed-bg); color: var(--removed-text); border-color: var(--error-border); text-decoration: line-through; font-weight: 400; opacity: 0.7; }
.tag[data-level="added"][data-original-level="confident"],
.tag[data-level="removed"][data-original-level="confident"] { font-weight: 600; }
```

### Tag Default State

Tags default to low confidence state (opacity 0.6) before classification:
```css
.tag {
    background-color: var(--low-bg);
    color: var(--low-text);
    opacity: 0.6;
    border: 1px solid transparent;
}
.tag[data-level="all"],
.tag[data-level="confident"],
.tag[data-level="added"],
.tag[data-level="removed"] {
    border-color: transparent;
    opacity: 1;
}
```

### Fade In Scale Animation

```css
@keyframes fadeInScale {
    from { opacity: 0; transform: scale(0.95); }
    to { opacity: 1; transform: scale(1); }
}
```

---

## Site Footer

```css
.site-info {
    text-align: center;
    margin-top: 2rem;
    font-size: 0.875rem;
    color: var(--low-text);
}
.site-info a { color: var(--confident-bg); text-decoration: none; }
```

---

## Tag Popup

### Popup Structure

```css
.tag-popup {
    position: absolute;
    background-color: var(--bg-color);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    box-shadow: 0 8px 24px var(--box-shadow-heavy);
    width: 280px;
    max-width: 80vw;
    z-index: 1000;
    backdrop-filter: blur(4px);
    animation: fadeInScale 0.2s;
}
```

### Popup Header

```css
.tag-popup-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border-color);
    font-weight: 600;
    background-color: var(--secondary-color);
    border-radius: 12px 12px 0 0;
}
.tag-popup-title {
    color: var(--confident-bg);
    word-break: break-word;
}
.close-popup {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-color);
    font-size: 1.2rem;
    padding: 0 0.25rem;
    border-radius: 4px;
    touch-action: manipulation;
}
```

### Popup Content

```css
.tag-popup-content {
    padding: 1rem;
    max-height: 300px;
    overflow-y: auto;
    font-size: 0.85rem;
    line-height: 1.5;
    color: var(--text-color);
}
.tag-popup-loading, .tag-popup-error {
    text-align: center;
    color: var(--low-text);
    font-style: italic;
}
.tag-popup-text {
    word-break: break-word;
    white-space: pre-wrap;
    user-select: text;
}
.tag-popup-text em { font-style: italic; }
.tag-popup-text u { text-decoration: underline; }
.tag-popup-text a { color: var(--primary-color); text-decoration: none; }
```

---

## Help Modal

### Modal Structure

```css
.help-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1100;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.2s ease, visibility 0.2s ease;
}
.help-modal.show {
    opacity: 1;
    visibility: visible;
}
```

### Modal Overlay

```css
.help-modal-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: var(--overlay-bg);
    backdrop-filter: blur(4px);
    opacity: 0;
    transition: opacity 0.2s ease;
}
.help-modal.show .help-modal-overlay { opacity: 1; }
```

### Modal Content

```css
.help-modal-content {
    position: relative;
    background-color: var(--bg-color);
    color: var(--text-color);
    border-radius: 12px;
    width: 90%;
    max-width: 800px;
    max-height: 80vh;
    overflow-y: auto;
    box-shadow: 0 8px 30px var(--box-shadow-heavyplus);
    border: 1px solid var(--border-color);
    transform: scale(0.9);
    opacity: 0;
    transition: transform 0.2s ease, opacity 0.2s ease;
}
.help-modal.show .help-modal-content {
    transform: scale(1);
    opacity: 1;
}
```

### Modal Header

```css
.help-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid var(--border-color);
}
.help-modal-header h2 {
    font-size: 1.2rem;
    font-weight: 500;
    color: var(--confident-bg);
    margin: 0;
}
.close-help-modal {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-color);
    font-size: 1.5rem;
    padding: 0;
    line-height: 1;
}
```

### Modal Body

```css
.help-modal-body {
    padding: 1.5rem;
    font-size: 0.9rem;
    line-height: 1.5;
}
.help-modal-body p { margin-bottom: 0.8rem; }
.help-modal-body strong, .tag-popup-text strong { font-weight: 600; color: var(--confident-bg); }
```

### Tag Examples in Help

```css
.tag-example {
    display: inline-block;
    padding: 0.1rem 0.4rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 500;
    margin: 0 0.2rem;
}
.tag-example.low { background-color: var(--low-bg); color: var(--low-text); }
```

### Help Footer

```css
.help-footer {
    margin-top: 1rem;
    font-size: 0.75rem;
    text-align: center;
    border-top: 1px solid var(--border-color);
    padding-top: 0.5rem;
}
.help-footer a {
    color: var(--confident-bg);
    text-decoration: none;
}
```

---

## Fullscreen Image Modal

### Modal Structure

```css
.fullscreen-image-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1200;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.2s ease, visibility 0.2s ease;
}
.fullscreen-image-modal.show {
    opacity: 1;
    visibility: visible;
}
```

### Modal Overlay (Animated blur "camera focus effect")

```css
.fullscreen-image-modal-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: var(--overlay-bg);
    backdrop-filter: blur(0px);
    opacity: 0;
    transition: opacity 0.2s ease, backdrop-filter 0.2s ease;
}
.fullscreen-image-modal.show .fullscreen-image-modal-overlay {
    opacity: 1;
    backdrop-filter: blur(4px);
}
```

### Image Container

```css
.fullscreen-image-container {
    position: relative;
    max-width: 90vw;
    max-height: 90vh;
    display: flex;
    align-items: center;
    justify-content: center;
}
.fullscreen-image {
    max-width: 100%;
    max-height: 90vh;
    object-fit: contain;
}
```

### Z-Index Reference

| Modal | z-index |
|-------|---------|
| Help Modal | 1100 |
| Fullscreen Image Modal | 1200 |

---

## Typography

### Base Font

```css
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: var(--bg-color);
    color: var(--text-color);
    line-height: 1.6;
}
```

### Headings

```css
h1 {
    font-size: 2.5rem;
    font-weight: 300;
    color: var(--confident-bg);
    line-height: 1.2;
}
h2 {
    font-size: 1.5rem;
    font-weight: 600;
}
```

---

## Accessibility

### Focus Styles

```css
input[type="number"]:hover::-webkit-inner-spin-button,
input[type="number"]:hover::-webkit-outer-spin-button {
    appearance: inner-spin-button;
    opacity: 0.5;
}

/* Theme-specific spinner inversions for visibility in dark/light modes */
.theme-light input[type="number"]::-webkit-inner-spin-button,
.theme-light input[type="number"]::-webkit-outer-spin-button { filter: invert(0); }
.theme-dark input[type="number"]::-webkit-inner-spin-button,
.theme-dark input[type="number"]::-webkit-outer-spin-button { filter: invert(1); }
```

### Visually Hidden

```css
.visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    border: 0;
}
```

---

## Integration Points

### HTML Classes

```html
<div id="dropZone">
<div id="settingsMenu" class="settings-menu">
<div class="results" id="results">
<div class="categories-container" id="categoriesContainer">
<div class="rating-display" id="ratingDisplay">
<div id="helpModal" class="help-modal">
<div class="egg-container">
<div class="theme-toggle-group">
<div class="format-toggle-group">
<div class="max-tags-group">
```

### JavaScript Integration

```javascript
// Toggle settings menu
document.getElementById('settingsMenu').classList.add('show');

// Set active preset
document.querySelector('.preset-btn.active').classList.remove('active');
document.querySelector(`[data-preset="${preset}"]`).classList.add('active');

// Change tag confidence level (IMPORTANT: uses data-level attribute)
document.querySelector('.tag').setAttribute('data-level', 'confident');

// Set theme
document.body.classList.add('theme-dark');

// Show results
document.getElementById('results').classList.add('visible');

// Change format
document.querySelector('.format-option.active').classList.remove('active');
document.querySelector(`[data-format="${format}"]`).classList.add('active');

// Toggle easter egg
document.querySelector('.egg-container').classList.add('open');
```

(End of file - ~1370 lines in source, 1369 lines in this doc)