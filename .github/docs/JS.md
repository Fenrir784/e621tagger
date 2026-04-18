# JavaScript Reference Documentation

This document provides a comprehensive reference for all methods, variables, and configurations in `static/js/script.js` (830 lines). It is designed for agent systems to understand and interact with the e621tagger frontend.

---

## File Overview

| Attribute | Value |
|-----------|-------|
| Location | `static/js/script.js` |
| Lines | ~1064 |
| Framework | Vanilla JavaScript |
| Purpose | Frontend UI functionality |
| Dependencies | Hammer.js (touch events), escapeHtml/sanitizeHtml/XSS protection |

### File Structure Flow

```
script.js (830 lines)
├── 1. Constants (27-35)           - Configuration values
├── 2. State Variables (37-53)     - Runtime application state
├── 3. DOM Cached (2-25)           - DOM element references
├── 4. preloadCreatures (55-58)    - Preload easter egg images
├── 5. loadSettings (60-96)        - Load from localStorage
├── 6. saveSettings (98-104)      - Save to localStorage
├── 7. UI Functions (105-220)       - Theme, notifications, popups
├── 8. XSS Protection (181-235)     - escapeHtml, sanitizeHtml, parseDText
├── 9. Tag Functions (237-376)     - Handle, display, filter tags
├── 10. Copy Functions (377-465)  - Clipboard, format conversion
├── 11. File Handling (466-572)     - Drag/drop, preview, validation
├── 12. initHammer (573-776)       - Hammer.js touch setup
├── 13. Event Listeners (777-830)   - Attach all listeners
└── 14. Final Init (825-830)      - Final setup
```

---

## 1. Constants

```javascript
const MAX_FILE_SIZE = 20 * 1024 * 1024;  // 20MB
const ALLOWED_MAX_TAGS = [50, 75, 100, 150, 200, 300];
const ratingTags = new Set(['safe', 'questionable', 'explicit']);
const creaturePaths = [
    '/static/icons/egg/f1.png', '/static/icons/egg/f2.png', '/static/icons/egg/f3.png',
    '/static/icons/egg/f4.png', '/static/icons/egg/f5.png', '/static/icons/egg/f6.png',
    '/static/icons/egg/f7.png', '/static/icons/egg/f8.png', '/static/icons/egg/f9.png'
];
const categoryOrder = ['Copyright', 'Character', 'Species', 'Meta', 'General', 'Lore'];
const tagDescriptionCache = new Map();  // Cache for e621 wiki tag descriptions
```

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_FILE_SIZE` | 20MB | Maximum upload file size |
| `ALLOWED_MAX_TAGS` | [50,75,100,150,200,300] | Valid top_k values |
| `ratingTags` | {safe, questionable, explicit} | Rating tag names |
| `creaturePaths` | 9 image paths | Easter egg creature images |
| `categoryOrder` | 6 categories | e621 display order |
| `tagDescriptionCache` | Map | Caches wiki descriptions to reduce API calls |

---

## 2. State Variables

```javascript
let allTags = [];                    // Tag predictions from API
let currentFormat = 'e621';         // 'e621' for danbooru format, any other for PostyBirb
let savedFormat = 'e621';           // 'e621' for danbooru format, any other for PostyBirb
let allThreshold = 0.55;           // Lower threshold (include)
let confidentThreshold = 0.75;      // Upper threshold (confident)
let currentTheme = 'system';          // 'system', 'light', 'dark'
let activePreset = 'standard';        // 'conservative'/'standard'/'liberal'/'custom'
let addedTags = new Set();           // User-added tags
let removedTags = new Set();         // User-removed tags
let maxTags = 200;                 // Max tags to request
let autoMetaTagSet = new Set();      // Auto-detected meta tags
let perTagAutoDisable = new Set();   // Per-tag auto disable
let currentPopup = null;            // Active popup DOM element
let activePopupTagElement = null;    // Popup trigger element
let pressBlockTap = false;           // Press event blocking flag
```

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `allTags` | Array | [] | Tag predictions from API |
| `currentFormat` | string | 'e621' | Runtime output format |
| `savedFormat` | string | 'e621' | Persisted default format |
| `allThreshold` | float | 0.55 | Include threshold |
| `confidentThreshold` | float | 0.75 | High confidence threshold |
| `currentTheme` | string | 'system' | UI theme |
| `activePreset` | string | 'standard' | Threshold preset |
| `addedTags` | Set | - | User-added tags |
| `removedTags` | Set | - | User-removed tags |
| `maxTags` | int | 200 | API top_k parameter |
| `autoMetaTagSet` | Set | - | Auto meta tags |
| `perTagAutoDisable` | Set | - | Disabled auto tags |

### Threshold Presets

```javascript
const presets = {
    conservative: { all: 0.65, confident: 0.85 },
    standard: { all: 0.55, confident: 0.75 },
    liberal: { all: 0.45, confident: 0.65 }
};
```

| Preset | allThreshold | confidentThreshold |
|--------|------------|-----------------|
| conservative | 0.65 | 0.85 |
| standard | 0.55 | 0.75 |
| liberal | 0.45 | 0.65 |
| custom | user-defined | user-defined |

---

## 3. DOM Cached Elements

| Element ID | Usage |
|------------|-------|
| `dropZone` | File upload area |
| `fileInput` | Hidden file input |
| `uploadContent` | Upload prompt text |
| `results` | Results container |
| `resultsContent` | Tags display area |
| `notification-container` | Toast notifications |
| `categoriesContainer` | Category tag groups |
| `ratingDisplay` | Rating badge |
| `copyGlobalAll` | Copy all button |
| `copyGlobalConfident` | Copy confident button |
| `settingsToggle` | Settings toggle button |
| `settingsMenu` | Settings panel |
| `closeSettings` | Close settings button |
| `presetBtns` | Threshold preset buttons |
| `customPanel` | Custom thresholds panel |
| `customAllInput` | Custom all threshold input |
| `customConfidentInput` | Custom confident threshold input |
| `applyCustom` | Apply custom button |
| `resetSettings` | Reset button |
| `eggContainer` | Easter egg container |
| `eggCreature` | Easter egg image |
| `helpBtn` | Help button |
| `helpModal` | Help modal |
| `closeHelpModalBtn` | Close help modal button |

---

## 4. Settings Functions

### preloadCreatures()

Preloads easter egg creature images for instant display.

```javascript
function preloadCreatures() {
    creaturePaths.forEach(path => { new Image().src = path; });
}
preloadCreatures();  // Called at initialization
```

### loadSettings()

Loads persisted settings from localStorage.

```javascript
function loadSettings() {
    const saved = localStorage.getItem('e621tagger-settings');
    if (saved) {
        const settings = JSON.parse(saved);
        allThreshold = settings.allThreshold ?? 0.55;
        confidentThreshold = settings.confidentThreshold ?? 0.75;
        savedFormat = settings.defaultFormat ?? 'e621';
        currentFormat = savedFormat;
        currentTheme = settings.theme ?? 'system';
        activePreset = settings.activePreset ?? 'standard';
        maxTags = settings.maxTags ?? 200;
        
        // Update UI
        updateTheme(currentTheme);
        updateThresholdUI();
    }
}
```

**IMPORTANT:** LocalStorage key is `e621tagger-settings` as a JSON string.

| localStorage Key | State Variable |
|----------------|--------------|
| allThreshold | allThreshold |
| confidentThreshold | confidentThreshold |
| defaultFormat | savedFormat, currentFormat |
| theme | currentTheme |
| activePreset | activePreset |
| maxTags | maxTags |

### saveSettings()

Persists settings to localStorage.

```javascript
function saveSettings() {
    localStorage.setItem('e621tagger-settings', JSON.stringify({
        allThreshold, confidentThreshold, defaultFormat: savedFormat,
        theme: currentTheme, activePreset, maxTags
    }));
}
```

### updateTheme(theme)

Applies theme class to document body.

```javascript
function updateTheme(theme) {
    currentTheme = theme;
    document.body.classList.remove('theme-light', 'theme-dark');
    if (theme === 'light') document.body.classList.add('theme-light');
    else if (theme === 'dark') document.body.classList.add('theme-dark');
}
```

### toggleSettings(show)

Shows or hides the settings panel.

```javascript
function toggleSettings(show) {
    settingsMenu.classList.toggle('show', show);
    settingsToggle.classList.toggle('open', show);
    if (show) positionSettingsMenu();
}

function positionSettingsMenu() {
    const toggleRect = settingsToggle.getBoundingClientRect();
    const containerRect = document.querySelector('.container').getBoundingClientRect();
    settingsMenu.style.left = (toggleRect.left - containerRect.left) + 'px';
    settingsMenu.style.top = (toggleRect.bottom - containerRect.top + 5) + 'px';
}
```

### updateThresholdUI()

Updates UI to reflect current threshold state.

```javascript
function updateThresholdUI() {
    presetBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.preset === activePreset);
    });
    customPanel.classList.toggle('open', activePreset === 'custom');
    customAllInput.value = allThreshold.toFixed(2);
    customConfidentInput.value = confidentThreshold.toFixed(2);
}
```

### updateLocalFormatUI()

Updates format toggle UI.

```javascript
function updateLocalFormatUI() {
    document.querySelectorAll('#resultsFormatToggle .format-option').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === currentFormat);
    });
}
```

---

## 5. XSS Protection Functions

### escapeHtml(unsafe)

Escapes HTML entities for safe display.

```javascript
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe.replace(/[&<>]/g, m => m === '&' ? '&amp;' : m === '<' ? '&lt;' : '&gt;');
}
```

### sanitizeHtml(html)

Removes dangerous HTML (event handlers, javascript:).

```javascript
function sanitizeHtml(html) {
    if (!html) return '';
    const dangerousAttrs = /\s+(on\w+|style\s*=\s*["']?(?:javascript:|expression\()[^"']*)/gi;
    let previous;
    // Remove disallowed tags
    do {
        previous = html;
        html = html.replace(/<(?!\/?(?:strong|em|u|sup|span|br)\b)[^>]*>/gi, (match) => {
            return match.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        });
    } while (html !== previous);
    // Remove dangerous attributes
    do {
        previous = html;
        html = html.replace(dangerousAttrs, '');
    } while (html !== previous);
    return html;
}
```

### parseDText(dtext)

Parses e621 wiki DText markup to HTML.

```javascript
function parseDText(dtext) {
    if (!dtext) return '';
    let text = escapeHtml(dtext.slice(0, 1000));
    // ... complex transformations for wiki markup
    return text;
}
```

---

## 6. Notification Functions

### showNotification(message, type, duration)

Shows a toast notification.

```javascript
function showNotification(message, type = 'error', duration = 3000) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notificationContainer.appendChild(notification);
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => notification.remove(), 300);
    }, duration);
}
```

| Type | CSS Class | Duration |
|------|----------|----------|
| error | .notification.error | 3000ms |
| success | .notification.success | 3000ms |
| info | .notification.info | 5000ms |

---

## 7. Tag Popup Functions

### fetchTagDescription(tagName)

Fetches tag description from e621 wiki API.

```javascript
async function fetchTagDescription(tagName) {
    if (tagDescriptionCache.has(tagName)) return tagDescriptionCache.get(tagName);
    const url = `https://e621.net/wiki_pages.json?search[title]=${encodeURIComponent(tagName)}&limit=1`;
    const response = await fetch(url, { headers: { 'User-Agent': 'e621tagger/1.0 (https://tagger.fenrir784.ru)' } });
    const data = await response.json();
    const result = data.length 
        ? { exists: true, title: data[0].title, body: data[0].body }
        : { exists: false, title: tagName, body: 'No description found on e621.' };
    tagDescriptionCache.set(tagName, result);
    return result;
}
```

**IMPORTANT:** Uses `/wiki_pages.json` endpoint, NOT `autocomplete.json`.

### showTagPopup(tagObj, targetElement)

Shows tag details popup with description.

```javascript
function showTagPopup(tagObj, targetElement) {
    if (currentPopup && activePopupTagElement === targetElement) return;
    if (currentPopup) closePopup();
    activePopupTagElement = targetElement;
    
    const tagName = tagObj.tag;
    const popup = document.createElement('div');
    popup.className = 'tag-popup';
    popup.innerHTML = `
        <div class="tag-popup-header">
            <a href="https://e621.net/wiki_pages?title=${escapeHtml(tagName)}" target="_blank">...</a>
            <button class="close-popup">✕</button>
        </div>
        <div class="tag-popup-content"><div class="tag-popup-loading">Loading...</div></div>
    `;
    document.body.appendChild(popup);
    currentPopup = popup;
    
    // Position popup
    // ... positioning code ...
    
    // Fetch description
    fetchTagDescription(tagName).then(desc => {
        const content = popup.querySelector('.tag-popup-content');
        if (desc.exists) content.innerHTML = `<div class="tag-popup-text">${sanitizeHtml(parseDText(desc.body))}</div>`;
        else content.innerHTML = `<div class="tag-popup-error">${escapeHtml(desc.body)}</div>`;
    });
}
```

### closePopup()

Closes the active tag popup.

```javascript
function closePopup() {
    if (currentPopup) {
        currentPopup.remove();
        currentPopup = null;
    }
    activePopupTagElement = null;
}
```

---

## 8. Tag Handling Functions

### handleTagClick(tagObj)

Handles tag click to toggle include/exclude state.

```javascript
function handleTagClick(tagObj) {
    if (pressBlockTap) return;
    const tag = tagObj.tag;
    const prob = tagObj.prob;
    const isConfident = prob >= confidentThreshold;
    const isAll = prob >= allThreshold;
    const wasAdded = addedTags.has(tag);
    const wasRemoved = removedTags.has(tag);
    
    if (isConfident) {
        if (!wasAdded && !wasRemoved) removedTags.add(tag);
        else if (wasRemoved) removedTags.delete(tag);
        else if (wasAdded) addedTags.delete(tag);
    } else if (isAll) {
        if (!wasAdded && !wasRemoved) addedTags.add(tag);
        else if (wasAdded) { addedTags.delete(tag); removedTags.add(tag); }
        else if (wasRemoved) removedTags.delete(tag);
    } else {
        if (!wasAdded && !wasRemoved) addedTags.add(tag);
        else if (wasAdded) addedTags.delete(tag);
        else if (wasRemoved) removedTags.delete(tag);
    }
    
    // Update all matching tag elements
    document.querySelectorAll(`.tag[data-tag="${tag}"]`).forEach(el => updateTagElement(el, tagObj));
    refreshTagClasses();
    updateCategoryButtonsDisabled();
}
```

| Current State | isConfident | isAll | Action |
|---------------|-------------|-------|--------|
| None | yes | - | Add to removedTags |
| None | - | yes | Add to addedTags |
| None | no | no | Add to addedTags |
| addedTags | yes | - | Remove from addedTags |
| addedTags | no | yes | Move to removedTags |
| removedTags | any | - | Remove from removedTags |

### updateTagElement(el, tagObj)

Updates a single tag element's data-level attribute.

```javascript
function updateTagElement(el, tagObj) {
    el.removeAttribute('data-level');
    if (addedTags.has(tagObj.tag)) el.setAttribute('data-level', 'added');
    else if (removedTags.has(tagObj.tag)) el.setAttribute('data-level', 'removed');
}
```

### refreshTagClasses()

Refreshes all tag elements' data-level attributes.

```javascript
function refreshTagClasses() {
    document.querySelectorAll('.tag').forEach(el => {
        const tagName = el.dataset.tag;
        const tagObj = allTags.find(t => t.tag === tagName);
        if (!tagObj) return;
        el.removeAttribute('data-level');
        if (addedTags.has(tagName)) el.setAttribute('data-level', 'added');
        else if (removedTags.has(tagName)) el.setAttribute('data-level', 'removed');
        else if (tagObj.prob >= confidentThreshold) el.setAttribute('data-level', 'confident');
        else if (tagObj.prob >= allThreshold) el.setAttribute('data-level', 'all');
    });
    updateCategoryButtonsDisabled();
}
```

### isTagIncluded(tagObj, threshold)

Determines if a tag should be included in output.

```javascript
function isTagIncluded(tagObj, threshold) {
    if (perTagAutoDisable.has(tagObj.tag)) return false;
    const tag = tagObj.tag;
    if (removedTags.has(tag)) return false;
    if (addedTags.has(tag)) return true;
    return tagObj.prob >= threshold;
}
```

### filterTags(threshold)

Filters tags by probability threshold.

```javascript
function filterTags(threshold) {
    return allTags.filter(t => !ratingTags.has(t.tag) && isTagIncluded(t, threshold));
}
```

### filterTagsByCategory(category, threshold)

Filters tags by category and threshold.

```javascript
function filterTagsByCategory(category, threshold) {
    return allTags.filter(t => t.category === category && !ratingTags.has(t.tag) && isTagIncluded(t, threshold));
}
```

### updateCategoryButtonsDisabled()

Updates disabled state of category copy buttons.

```javascript
function updateCategoryButtonsDisabled() {
    document.querySelectorAll('.cat-copy-btn').forEach(btn => {
        const category = btn.dataset.category;
        const type = btn.dataset.type;
        const threshold = type === 'confident' ? confidentThreshold : allThreshold;
        const categoryTags = allTags.filter(t => t.category === category && !ratingTags.has(t.tag));
        const hasAny = categoryTags.some(t => isTagIncluded(t, threshold));
        btn.disabled = !hasAny;
    });
}
```

### displayTags(tags)

Main tag rendering function - creates DOM elements.

```javascript
function displayTags(tags) {
    let rating = null;
    const nonRatingTags = [];
    
    // Separate rating and non-rating tags
    tags.forEach(t => {
        if (ratingTags.has(t.tag)) {
            if (!rating || t.prob > rating.prob) rating = t;
        } else nonRatingTags.push(t);
    });
    
    // Render rating badge
    if (rating) {
        ratingDisplay.textContent = `Rating: ${rating.tag}`;
        ratingDisplay.className = 'rating-display ' + rating.tag;
    }
    
    // Group by category
    const grouped = {};
    nonRatingTags.sort((a, b) => b.prob - a.prob);
    nonRatingTags.forEach(item => {
        const cat = item.category || 'Other';
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push(item);
    });
    
    // Render categories
    categoriesContainer.innerHTML = '';
    Object.keys(grouped).sort(/* category order sort */).forEach(cat => {
        // Create category block with tags
        // Attach Hammer.js events
    });
}
```

---

## 9. Tag States (CSS data-level)

**IMPORTANT:** Tags use `data-level` attribute, NOT CSS classes.

```javascript
// Setting data-level attribute
el.setAttribute('data-level', 'confident');  // High confidence
el.setAttribute('data-level', 'all');       // Above all threshold
el.setAttribute('data-level', 'added');     // User added
el.setAttribute('data-level', 'removed');   // User removed
```

| data-level | Condition | CSS Variable |
|-----------|----------|-------------|
| confident | prob >= confidentThreshold | --confident-bg (purple) |
| all | prob >= allThreshold | --all-bg (blue) |
| added | addedTags.has(tag) | --added-bg (green) |
| removed | removedTags.has(tag) | --removed-bg (red) |
| (none) | Below allThreshold | --low-bg (gray) |

---

## 10. Copy Functions

### formatTags(tags)

Formats tags for clipboard output.

```javascript
function formatTags(tags) {
    if (currentFormat === 'e621') {
        // Group by category, sort categories, join with space
        const grouped = {};
        tags.forEach(t => {
            const cat = t.category || 'Other';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(t.tag);
        });
        // Sort categories by categoryOrder
        const sortedCats = Object.keys(grouped).sort((a, b) => {
            const ia = categoryOrder.indexOf(a);
            const ib = categoryOrder.indexOf(b);
            // ... sorting logic
            return /* result */;
        });
        return sortedCats.map(cat => grouped[cat].join(' ')).join('\n');
    } else {
        // posty format - replace underscores with spaces
        return tags.map(t => t.tag.replace(/_/g, ' ')).join(', ');
    }
}
```

| Format | Internal Value | Separator | Example Output |
|--------|---------------|-----------|-------------|
| e621 | `'e621'` (danbooru) | space | `female anthro solo` (per line) |
| PostyBirb | any other value | comma | `female, anthro, solo` |

### copyToClipboard(text, count, format, btn)

Copies text to clipboard with auto-meta tags.

```javascript
async function copyToClipboard(text, count, format, btn) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
            let finalText = text;
            // Add auto-meta tags
            if (autoMetaTagSet && autoMetaTagSet.size > 0) {
                const extras = [];
                autoMetaTagSet.forEach(t => {
                    if (perTagAutoDisable.has(t)) return;
                    if (text.includes(t) || text.includes(t.replace(/_/g, ' '))) return;
                    extras.push(t);
                });
                if (extras.length > 0) {
                    const joiner = (format === 'e621') ? ' ' : ', ';
                    finalText = finalText ? finalText + joiner + extras.join(joiner) : extras.join(joiner);
                }
            }
            await navigator.clipboard.writeText(finalText);
            showCopySuccess(btn, count, format);
        } catch { fallbackCopy(text, btn, count, format); }
    } else { fallbackCopy(text, btn, count, format); }
}
```

### fallbackCopy(text, btn, count, format)

Fallback clipboard copy for older browsers.

```javascript
function fallbackCopy(text, btn, count, format) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
        if (document.execCommand('copy')) showCopySuccess(btn, count, format);
        else showNotification('Unable to copy.', 'error');
    } catch { showNotification('Copy failed.', 'error'); }
    document.body.removeChild(textarea);
}
```

### showCopySuccess(btn, count, format)

Shows copy success state on button.

```javascript
function showCopySuccess(btn, count, format) {
    if (btn._copyTimeout) clearTimeout(btn._copyTimeout);
    btn.classList.add('copied');
    const displayName = format === 'e621' ? 'e621' : 'PostyBirb';
    showNotification(`Copied ${count} tags • ${displayName}`, 'success');
    btn._copyTimeout = setTimeout(() => btn.classList.remove('copied'), 1000);
}
```

---

## 11. File Handling Functions

### handleFiles(files)

Processes uploaded files.

```javascript
function handleFiles(files) {
    if (files.length === 0) return;
    const file = files[0];
    if (!file.type.startsWith('image/')) {
        showNotification('Please select an image file.', 'error');
        return;
    }
    if (file.size > MAX_FILE_SIZE) {
        showNotification(`File too large. Maximum size is ${MAX_FILE_SIZE / (1024*1024)}MB.`, 'error');
        return;
    }
    showPreview(file);
}
```

### showPreview(file)

Shows image preview and fetches tags.

```javascript
async function showPreview(file) {
    // Remove existing image
    const existingImg = dropZone.querySelector('img');
    if (existingImg) existingImg.remove();
    
    uploadContent.style.display = 'none';
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    img.alt = 'Preview';
    img.onload = function() {
        img.width = img.naturalWidth;
        img.height = img.naturalHeight;
    };
    dropZone.appendChild(img);
    dropZone.classList.add('has-image');
    
    // Fetch tags
    await uploadImage(file);
}
```

### uploadImage(file)

Uploads image to API and processes response.

```javascript
async function uploadImage(file) {
    dropZone.classList.add('processing');
    
    const formData = new FormData();
    formData.append('image', file);
    formData.append('top_k', maxTags.toString());
    
    const response = await fetch('/predict', {
        method: 'POST',
        body: formData
    });
    
    const result = await response.json();
    
    if (result.success) {
        allTags = result.tags;
        autoMetaTagSet = new Set(result.auto_meta || []);
        addedTags.clear();
        removedTags.clear();
        await showResults();
        displayTags(allTags);
        showNotification(`Generated ${allTags.length} tags`, 'success');
    } else {
        showNotification(result.error || 'Failed to process image', 'error');
    }
    
    dropZone.classList.remove('processing');
}
```

---

## 12. Hammer.js Setup Functions

### attachHammerTap(element, handler)

Attaches Hammer.js tap event handler.

```javascript
function attachHammerTap(element, handler) {
    if (element._hammer) element._hammer.destroy();
    const hammer = new Hammer(element);
    hammer.on('tap', handler);
    element._hammer = hammer;
}
```

### initHammer()

Initializes Hammer.js for all interactive elements.

```javascript
function initHammer() {
    // Settings toggle
    attachHammerTap(settingsToggle, () => toggleSettings(!settingsMenu.classList.contains('show')));
    
    // Close settings
    attachHammerTap(closeSettings, () => toggleSettings(false));
    
    // Reset button
    attachHammerTap(resetBtn, () => {
        allThreshold = 0.55; confidentThreshold = 0.75;
        savedFormat = 'e621'; currentFormat = savedFormat;
        currentTheme = 'system'; activePreset = 'standard'; maxTags = 200;
        updateTheme('system');
        applyThresholds();
        saveSettings();
    });
    
    // Preset buttons
    presetBtns.forEach(btn => {
        attachHammerTap(btn, () => {
            const preset = btn.dataset.preset;
            if (preset === 'custom') {
                activePreset = 'custom';
                updateThresholdUI();
                saveSettings();
                return;
            }
            activePreset = preset;
            switch (preset) {
                case 'conservative': allThreshold = 0.65; confidentThreshold = 0.85; break;
                case 'standard': allThreshold = 0.55; confidentThreshold = 0.75; break;
                case 'liberal': allThreshold = 0.45; confidentThreshold = 0.65; break;
            }
            customAllInput.value = allThreshold.toFixed(2);
            customConfidentInput.value = confidentThreshold.toFixed(2);
            applyThresholds();
        });
    });
    
    // Theme toggle
    document.querySelectorAll('#themeToggle .theme-option').forEach(btn => {
        attachHammerTap(btn, () => {
            document.querySelectorAll('#themeToggle .theme-option').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTheme = btn.dataset.value;
            updateTheme(currentTheme);
            saveSettings();
        });
    });
    
    // More toggle setup...
}
```

---

## 13. Results Display Functions

### hideResults()

Hides results container with animation.

```javascript
async function hideResults() {
    if (!results.classList.contains('visible')) return Promise.resolve();
    results.classList.remove('visible');
    return new Promise(resolve => {
        const onTransitionEnd = () => {
            results.style.display = 'none';
            results.removeEventListener('transitionend', onTransitionEnd);
            resolve();
        };
        results.addEventListener('transitionend', onTransitionEnd, { once: true });
    });
}
```

### showResults()

Shows results container.

```javascript
async function showResults() {
    if (results.classList.contains('visible')) return Promise.resolve();
    results.style.display = 'block';
    // Force reflow
    results.offsetHeight;
    results.classList.add('visible');
}
```

### applyThresholds()

Applies threshold settings and re-renders.

```javascript
function applyThresholds() {
    if (allTags.length) {
        refreshTagClasses();
        setupCategoryCopyButtons();
    }
    updateThresholdUI();
    saveSettings();
}
```

---

## 14. Event Listeners

### File Input Events

```javascript
// Prevent defaults
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => 
    dropZone.addEventListener(eventName, preventDefaults, false));

// Drag visual feedback
['dragenter', 'dragover'].forEach(eventName => 
    dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false));
['dragleave', 'drop'].forEach(eventName => 
    dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false));

// Drop handler
dropZone.addEventListener('drop', (e) => handleFiles(e.dataTransfer.files));

// File input
fileInput.addEventListener('change', () => handleFiles(fileInput.files));

// Paste
document.addEventListener('paste', (e) => {
    const items = e.clipboardData?.items;
    for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.type.startsWith('image/')) {
            const file = item.getAsFile();
            if (file) { handleFiles([file]); break; }
        }
    }
});

// Click outside to close
document.addEventListener('click', (e) => {
    if (currentPopup && !currentPopup.contains(e.target)) closePopup();
    if (!settingsMenu.contains(e.target) && !settingsToggle.contains(e.target)) toggleSettings(false);
});

// Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closePopup();
        toggleSettings(false);
    }
});
```

---

## 15. API Reference

### /predict Endpoint

| Method | Path | Purpose |
|--------|------|---------|
| POST | /predict | Tag image |

### Request Format

```
POST /predict
Content-Type: multipart/form-data

image: <File>
top_k: <number> (optional, default 200)
```

### Response Format

```json
{
  "success": true,
  "tags": [
    { "tag": "string", "prob": 0.0-1.0, "category": "string" }
  ],
  "auto_meta": ["string"]
}
```

### API Response Structure

| Field | Type | Description |
|-------|------|-------------|
| success | boolean | Success status |
| tags | array | Tag predictions |
| tags[].tag | string | Tag name |
| tags[].prob | float | Probability (0-1) |
| tags[].category | string | e621 category |
| auto_meta | array | Auto-detected tags |

---

## 16. Quick Reference for Agents

### LocalStorage

| Key | Type | Description |
|-----|------|-------------|
| e621tagger-settings | JSON | All persisted settings |

**IMPORTANT:** The key is `e621tagger-settings` (single JSON key), NOT individual keys.

### Error Handling

| Error | Message |
|-------|----------|
| Not an image | "Please select an image file." |
| File too large | "File too large. Maximum size is 20MB." |
| API error | Shows result.error |

### Tag States

| data-level | CSS Variable | Color |
|-----------|-----------|-------|
| confident | --confident-bg | Purple |
| all | --all-bg | Blue |
| added | --added-bg | Green |
| removed | --removed-bg | Red |
| (none) | --low-bg | Gray |

### HTML Element IDs

| ID | Element |
|----|---------|
| dropZone | File drop area |
| fileInput | Hidden file input |
| results | Results container |
| categoriesContainer | Category tags |
| ratingDisplay | Rating badges |
| settingsMenu | Settings panel |
| helpModal | Help overlay |
| notification-container | Toast container |

(End of file - total ~780 lines)