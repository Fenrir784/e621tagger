document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const uploadContent = document.getElementById('uploadContent');
    const results = document.getElementById('results');
    const resultsContent = document.getElementById('resultsContent');
    const notificationContainer = document.getElementById('notification-container');
    const categoriesContainer = document.getElementById('categoriesContainer');
    const ratingDisplay = document.getElementById('ratingDisplay');
    const copyGlobalAll = document.getElementById('copyGlobalAll');
    const copyGlobalConfident = document.getElementById('copyGlobalConfident');
    const settingsToggle = document.getElementById('settingsToggle');
    const settingsMenu = document.getElementById('settingsMenu');
    const closeSettings = document.getElementById('closeSettings');
    const presetBtns = document.querySelectorAll('.preset-btn');
    const customPanel = document.getElementById('customThresholdsPanel');
    const customAllInput = document.getElementById('customAll');
    const customConfidentInput = document.getElementById('customConfident');
    const applyCustom = document.getElementById('applyCustom');
    const resetBtn = document.getElementById('resetSettings');
    const eggContainer = document.getElementById('eggContainer');
    const eggCreature = document.getElementById('eggCreature');
    const helpBtn = document.getElementById('helpThresholdsBtn');
    const helpModal = document.getElementById('helpModal');
    const closeHelpModalBtn = document.querySelector('.close-help-modal');

    const MAX_FILE_SIZE = 20 * 1024 * 1024;
    const ALLOWED_MAX_TAGS = [50, 75, 100, 150, 200, 300];
    const ratingTags = new Set(['safe', 'questionable', 'explicit']);
    const creaturePaths = [
        '/static/icons/egg/f1.png', '/static/icons/egg/f2.png', '/static/icons/egg/f3.png',
        '/static/icons/egg/f4.png', '/static/icons/egg/f5.png', '/static/icons/egg/f6.png',
        '/static/icons/egg/f7.png', '/static/icons/egg/f8.png', '/static/icons/egg/f9.png'
    ];
    const categoryOrder = ['Copyright', 'Character', 'Species', 'Meta', 'General', 'Lore'];

    let allTags = [];
    let currentFormat = 'e621';
    let savedFormat = 'e621';
    let allThreshold = 0.55;
    let confidentThreshold = 0.75;
    let currentTheme = 'system';
    let activePreset = 'standard';
    let addedTags = new Set();
    let removedTags = new Set();
    let maxTags = 200;
    let autoMetaTagSet = new Set();
    let perTagAutoDisable = new Set();

    const tagDescriptionCache = new Map();
    let currentPopup = null;
    let activePopupTagElement = null;
    let pressBlockTap = false;

    function preloadCreatures() {
        creaturePaths.forEach(path => { new Image().src = path; });
    }
    preloadCreatures();

    function loadSettings() {
        const saved = localStorage.getItem('e621tagger-settings');
        if (saved) {
            try {
                const settings = JSON.parse(saved);
                allThreshold = settings.allThreshold ?? 0.55;
                confidentThreshold = settings.confidentThreshold ?? 0.75;
                savedFormat = settings.defaultFormat ?? 'e621';
                currentFormat = savedFormat;
                currentTheme = settings.theme ?? 'system';
                activePreset = settings.activePreset ?? 'standard';
                maxTags = settings.maxTags ?? 200;
                if (!ALLOWED_MAX_TAGS.includes(maxTags)) maxTags = 200;
                
                document.querySelectorAll('#themeToggle .theme-option').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.value === currentTheme);
                });
                
                document.querySelectorAll('#defaultFormatToggle .format-option').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.value === savedFormat);
                });
                
                document.querySelectorAll('#maxTagsToggle .max-tag-option').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.value === String(maxTags));
                });
                
                updateTheme(currentTheme);
                updateThresholdUI();
            } catch (e) {
                console.warn('Failed to load settings', e);
            }
        } else {
            activePreset = 'standard';
            maxTags = 200;
            updateThresholdUI();
        }
    }

    function saveSettings() {
        localStorage.setItem('e621tagger-settings', JSON.stringify({
            allThreshold, confidentThreshold, defaultFormat: savedFormat,
            theme: currentTheme, activePreset, maxTags
        }));
    }

    function updateTheme(theme) {
        currentTheme = theme;
        document.body.classList.remove('theme-light', 'theme-dark');
        if (theme === 'light') document.body.classList.add('theme-light');
        else if (theme === 'dark') document.body.classList.add('theme-dark');
    }

    function updateLocalFormatUI() {
        document.querySelectorAll('#resultsFormatToggle .format-option').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.value === currentFormat);
        });
    }

    function updateThresholdUI() {
        presetBtns.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.preset === activePreset);
        });
        customPanel.classList.toggle('open', activePreset === 'custom');
        customAllInput.value = allThreshold.toFixed(2);
        customConfidentInput.value = confidentThreshold.toFixed(2);
    }

    function refreshTagClasses() {
        document.querySelectorAll('.tag').forEach(el => {
            const tagName = el.dataset.tag;
            const tagObj = allTags.find(t => t.tag === tagName);
            if (!tagObj) return;
            el.removeAttribute('data-level');
            if (addedTags.has(tagName)) {
                el.setAttribute('data-level', 'added');
            } else if (removedTags.has(tagName)) {
                el.setAttribute('data-level', 'removed');
            } else if (tagObj.prob >= confidentThreshold) {
                el.setAttribute('data-level', 'confident');
            } else if (tagObj.prob >= allThreshold) {
                el.setAttribute('data-level', 'all');
            }
        });
        updateCategoryButtonsDisabled();
    }

    function applyThresholds() {
        if (allTags.length) {
            refreshTagClasses();
            setupCategoryCopyButtons();
        }
        updateThresholdUI();
        saveSettings();
    }

    function toggleSettings(show) {
        settingsMenu.classList.toggle('show', show);
        settingsToggle.classList.toggle('open', show);
        if (show) {
            positionSettingsMenu();
        }
    }

    function positionSettingsMenu() {
        const toggleRect = settingsToggle.getBoundingClientRect();
        const containerRect = document.querySelector('.container').getBoundingClientRect();
        settingsMenu.style.left = (toggleRect.left - containerRect.left) + 'px';
        settingsMenu.style.top = (toggleRect.bottom - containerRect.top + 5) + 'px';
    }

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

    function escapeHtml(unsafe) {
        if (!unsafe) return '';
        return unsafe.replace(/[&<>]/g, m => m === '&' ? '&amp;' : m === '<' ? '&lt;' : '&gt;');
    }

    function sanitizeHtml(html) {
        if (!html) return '';
        const dangerousAttrs = /\s+(on\w+|style\s*=\s*["']?(?:javascript:|expression\()[^"']*)/gi;
        let previous;
        do {
            previous = html;
            html = html.replace(/<(?!\/?(?:strong|em|u|sup|span|br)\b)[^>]*>/gi, (match) => {
                return match.replace(/</g, '&lt;').replace(/>/g, '&gt;');
            });
        } while (html !== previous);
        do {
            previous = html;
            html = html.replace(dangerousAttrs, '');
        } while (html !== previous);
        return html;
    }

    function parseDText(dtext) {
        if (!dtext) return '';
        let text = escapeHtml(dtext.slice(0, 1000));
        text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
        text = text.replace(/thumb\s+#\d+\s*/g, '');
        text = text.replace(/\[section[^\]]*\]([\s\S]*?)\[\/section\]/g, '$1');
        text = text.replace(/\[quote[^\]]*\]([\s\S]*?)\[\/quote\]/g, '$1');
        text = text.replace(/\[table[^\]]*\]([\s\S]*?)\[\/table\]/g, '$1');
        text = text.replace(/\[s\]([\s\S]*?)\[\/s\]/g, '$1');
        text = text.replace(/\[color=([^\]]+)\]([\s\S]*?)\[\/color\]/g, '<span style="color: var(--confident-bg);">$2</span>');
        text = text.replace(/"([^"]+)"\s*:\s*(\S+)/g, (match, linkText) => `<span style="color: var(--confident-bg);">${linkText}</span>`);
        text = text.replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, (match, target, display) => `<span style="color: var(--confident-bg);">${display}</span>`);
        text = text.replace(/\[\[([^\]]+)\]\]/g, (match, p1) => `<span style="color: var(--confident-bg);">${p1}</span>`);
        let lines = text.split('\n');
        let processedLines = [];
        for (let line of lines) {
            let trimmed = line;
            const headerMatch = trimmed.match(/^\s*h([1-6])(?:\.?\s*)(.*)$/i);
            if (headerMatch) trimmed = `<strong style="color: var(--confident-bg);">${headerMatch[2]}</strong>`;
            else trimmed = trimmed.replace(/^(\*+)\s+/, '');
            if (trimmed.trim() !== '') processedLines.push(trimmed);
        }
        text = processedLines.join('\n');
        text = text.replace(/\[b\]([\s\S]*?)\[\/b\]/g, '<strong>$1</strong>');
        text = text.replace(/\[i\]([\s\S]*?)\[\/i\]/g, '<em>$1</em>');
        text = text.replace(/\[u\]([\s\S]*?)\[\/u\]/g, '<u>$1</u>');
        text = text.replace(/\[sup\]([\s\S]*?)\[\/sup\]/g, '<sup>$1</sup>');
        text = text.replace(/\n/g, '<br>');
        text = text.replace(/(<br>){3,}/g, '<br><br>');
        text = text.replace(/^(<br>)+/, '').replace(/(<br>)+$/, '');
        if (dtext.length > 1000) text += '…';
        return text;
    }

    async function fetchTagDescription(tagName) {
        if (tagDescriptionCache.has(tagName)) return tagDescriptionCache.get(tagName);
        const url = `https://e621.net/wiki_pages.json?search[title]=${encodeURIComponent(tagName)}&limit=1`;
        try {
            const response = await fetch(url, { headers: { 'User-Agent': 'e621tagger/1.0 (https://tagger.fenrir784.ru)' } });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            if (data && data.length) {
                const wiki = data[0];
                const result = { exists: true, title: wiki.title || tagName, body: wiki.body || 'No description available.' };
                tagDescriptionCache.set(tagName, result);
                return result;
            } else {
                const result = { exists: false, title: tagName, body: 'No description found on e621.' };
                tagDescriptionCache.set(tagName, result);
                return result;
            }
        } catch (err) {
            console.warn(`Failed to fetch description for ${tagName}:`, err);
            return { exists: false, title: tagName, body: 'Failed to load description. Please check your internet connection.' };
        }
    }

    function closePopup() {
        if (currentPopup) {
            currentPopup.remove();
            currentPopup = null;
        }
        activePopupTagElement = null;
    }

    function showTagPopup(tagObj, targetElement) {
        if (currentPopup && activePopupTagElement === targetElement) return;
        if (currentPopup) closePopup();
        activePopupTagElement = targetElement;
        const tagName = tagObj.tag;
        const popup = document.createElement('div');
        popup.className = 'tag-popup';
        const wikiUrl = `https://e621.net/wiki_pages?title=${encodeURIComponent(tagName)}`;
        popup.innerHTML = `
            <div class="tag-popup-header">
                <a href="${wikiUrl}" target="_blank" rel="noopener noreferrer" style="display: flex; align-items: center; gap: 8px; text-decoration: none; color: var(--confident-bg);">
                    <span>${escapeHtml(tagName)}</span>
                    <span style="color: var(--low-text); font-size: 0.7rem; text-decoration: underline;">read more</span>
                </a>
                <button class="close-popup">✕</button>
            </div>
            <div class="tag-popup-content"><div class="tag-popup-loading">Loading description...</div></div>
        `;
        document.body.appendChild(popup);
        currentPopup = popup;
        const rect = targetElement.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        popup.style.visibility = 'hidden';
        popup.style.position = 'absolute';
        const popupRect = popup.getBoundingClientRect();
        popup.style.visibility = '';
        let top = rect.bottom + 8;
        let left = rect.left + (rect.width / 2) - (popupRect.width / 2);
        if (top + popupRect.height > viewportHeight - 10) top = rect.top - popupRect.height - 8;
        left = Math.max(10, Math.min(left, viewportWidth - popupRect.width - 10));
        popup.style.top = `${top + window.scrollY}px`;
        popup.style.left = `${left + window.scrollX}px`;
        const closeBtn = popup.querySelector('.close-popup');
        closeBtn.addEventListener('click', () => closePopup());
        fetchTagDescription(tagName).then(desc => {
            const content = popup.querySelector('.tag-popup-content');
            if (desc.exists) content.innerHTML = `<div class="tag-popup-text">${sanitizeHtml(parseDText(desc.body))}</div>`;
            else content.innerHTML = `<div class="tag-popup-error">${escapeHtml(desc.body)}</div>`;
        }).catch(() => {
            popup.querySelector('.tag-popup-content').innerHTML = '<div class="tag-popup-error">Failed to load description.</div>';
        });
    }

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
        document.querySelectorAll(`.tag[data-tag="${tag}"]`).forEach(el => updateTagElement(el, tagObj));
        refreshTagClasses();
        updateCategoryButtonsDisabled();
    }

    function updateTagElement(el, tagObj) {
        el.removeAttribute('data-level');
        if (addedTags.has(tagObj.tag)) el.setAttribute('data-level', 'added');
        else if (removedTags.has(tagObj.tag)) el.setAttribute('data-level', 'removed');
    }

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

    function isTagIncluded(tagObj, threshold) {
        if (perTagAutoDisable.has(tagObj.tag)) return false;
        const tag = tagObj.tag;
        if (removedTags.has(tag)) return false;
        if (addedTags.has(tag)) return true;
        return tagObj.prob >= threshold;
    }

    function filterTags(threshold) {
        return allTags.filter(t => !ratingTags.has(t.tag) && isTagIncluded(t, threshold));
    }

    function filterTagsByCategory(category, threshold) {
        return allTags.filter(t => t.category === category && !ratingTags.has(t.tag) && isTagIncluded(t, threshold));
    }

    function formatTags(tags) {
        if (currentFormat === 'e621') {
            const grouped = {};
            tags.forEach(t => {
                const cat = t.category || 'Other';
                if (!grouped[cat]) grouped[cat] = [];
                grouped[cat].push(t.tag);
            });
            const sortedCats = Object.keys(grouped).sort((a, b) => {
                const ia = categoryOrder.indexOf(a);
                const ib = categoryOrder.indexOf(b);
                if (ia !== -1 && ib !== -1) return ia - ib;
                if (ia !== -1) return -1;
                if (ib !== -1) return 1;
                return a.localeCompare(b);
            });
            return sortedCats.map(cat => grouped[cat].join(' ')).join('\n');
        } else {
            return tags.map(t => t.tag.replace(/_/g, ' ')).join(', ');
        }
    }

    async function copyToClipboard(text, count, format, btn) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            try {
                let finalText = text;
                if (autoMetaTagSet && autoMetaTagSet.size > 0) {
                    const extras = [];
                    autoMetaTagSet.forEach(t => {
                        if (perTagAutoDisable.has(t)) return;
                        if (text.includes(t) || text.includes(t.replace(/_/g, ' '))) return;
                        extras.push(t);
                    });
                    if (extras.length > 0) {
                        const joiner = (format === 'e621') ? ' ' : ', ';
                        finalText = finalText ? finalText + (joiner) + extras.join(joiner) : extras.join(joiner);
                    }
                }
                await navigator.clipboard.writeText(finalText);
                showCopySuccess(btn, count, format);
            } catch { fallbackCopy(text, btn, count, format); }
        } else { fallbackCopy(text, btn, count, format); }
    }

    function showCopySuccess(btn, count, format) {
        if (btn._copyTimeout) clearTimeout(btn._copyTimeout);
        btn.classList.add('copied');
        const displayName = format === 'e621' ? 'e621' : 'PostyBirb';
        showNotification(`📋 Copied ${count} ${count === 1 ? 'tag' : 'tags'} • ${displayName}`, 'success');
        btn._copyTimeout = setTimeout(() => btn.classList.remove('copied'), 1000);
    }

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

    function setupGlobalCopyButton(btn, getThreshold) {
        const hammer = new Hammer(btn);
        hammer.on('tap', async () => {
            const threshold = getThreshold();
            const filtered = filterTags(threshold);
            if (filtered.length === 0) { showNotification('No tags meet the threshold.', 'error'); return; }
            const text = formatTags(filtered);
            await copyToClipboard(text, filtered.length, currentFormat, btn);
        });
    }

    function setupCategoryCopyButtons() {
        document.querySelectorAll('.cat-copy-btn').forEach(btn => {
            if (btn._hammer) btn._hammer.destroy();
            const hammer = new Hammer(btn);
            const category = btn.dataset.category;
            const type = btn.dataset.type;
            const threshold = type === 'confident' ? confidentThreshold : allThreshold;
            hammer.on('tap', async () => {
                if (btn.disabled) return;
                const filtered = filterTagsByCategory(category, threshold);
                if (filtered.length === 0) { showNotification(`No ${type} tags in ${category}.`, 'error'); return; }
                const text = formatTags(filtered);
                await copyToClipboard(text, filtered.length, currentFormat, btn);
            });
            btn._hammer = hammer;
        });
    }

    function attachTagEvents(tagEl, tagObj) {
        if (tagEl._hammer) tagEl._hammer.destroy();
        let pressTimer = null;
        const hammer = new Hammer(tagEl);
        hammer.on('tap', (e) => {
            if (pressBlockTap) {
                pressBlockTap = false;
                return;
            }
            handleTagClick(tagObj);
        });
        hammer.on('press', (e) => {
            e.srcEvent.preventDefault();
            if (pressTimer) clearTimeout(pressTimer);
            pressBlockTap = true;
            pressTimer = setTimeout(() => {
                pressBlockTap = false;
                pressTimer = null;
            }, 500);
            showTagPopup(tagObj, tagEl);
        });
        tagEl.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            if (!pressBlockTap) showTagPopup(tagObj, tagEl);
        });
        tagEl._hammer = hammer;
    }

    function displayTags(tags) {
        let rating = null;
        const nonRatingTags = [];
        tags.forEach(t => {
            if (ratingTags.has(t.tag)) {
                if (!rating || t.prob > rating.prob) rating = t;
            } else nonRatingTags.push(t);
        });
        if (rating) {
            ratingDisplay.textContent = `Rating: ${rating.tag}`;
            ratingDisplay.className = 'rating-display ' + rating.tag;
            ratingDisplay.style.display = 'inline-block';
        } else ratingDisplay.style.display = 'none';

        const grouped = {};
        nonRatingTags.sort((a, b) => b.prob - a.prob);
        nonRatingTags.forEach(item => {
            const cat = item.category || 'Other';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(item);
        });

        categoriesContainer.innerHTML = '';
        Object.keys(grouped).sort((a, b) => {
            const ia = categoryOrder.indexOf(a);
            const ib = categoryOrder.indexOf(b);
            if (ia !== -1 && ib !== -1) return ia - ib;
            if (ia !== -1) return -1;
            if (ib !== -1) return 1;
            return a.localeCompare(b);
        }).forEach(cat => {
            const catTags = grouped[cat];
            const catDiv = document.createElement('div');
            catDiv.className = 'category-block';
            catDiv.innerHTML = `
                <div class="category-header">
                    <span class="category-name">${escapeHtml(cat)}</span>
                    <div class="category-buttons">
                        <button type="button" class="cat-copy-btn confident" data-category="${escapeHtml(cat)}" data-type="confident" title="Copy confident tags">C</button>
                        <button type="button" class="cat-copy-btn all" data-category="${escapeHtml(cat)}" data-type="all" title="Copy all tags">A</button>
                    </div>
                </div>
                <div class="category-tags"></div>
            `;
            const tagsContainer = catDiv.querySelector('.category-tags');
            catTags.forEach(item => {
                const tagEl = document.createElement('span');
                tagEl.className = 'tag';
                tagEl.setAttribute('data-tag', item.tag);
                tagEl.textContent = item.tag;
                if (addedTags.has(item.tag)) {
                    tagEl.setAttribute('data-level', 'added');
                } else if (removedTags.has(item.tag)) {
                    tagEl.setAttribute('data-level', 'removed');
                } else if (item.prob >= confidentThreshold) {
                    tagEl.setAttribute('data-level', 'confident');
                    tagEl.setAttribute('data-original-level', 'confident');
                } else if (item.prob >= allThreshold) {
                    tagEl.setAttribute('data-level', 'all');
                }
                
                attachTagEvents(tagEl, item);
                tagsContainer.appendChild(tagEl);
            });
            categoriesContainer.appendChild(catDiv);
        });
        setupCategoryCopyButtons();
    }

    function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }

    function handleFiles(files) {
        if (files.length === 0) return;
        const file = files[0];
        if (!file.type.startsWith('image/')) { showNotification('Please select an image file.', 'error'); return; }
        if (file.size > MAX_FILE_SIZE) { showNotification(`File too large. Maximum size is ${MAX_FILE_SIZE / (1024*1024)}MB.`, 'error'); return; }
        uploadImage(file);
    }

    function showPreview(file) {
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
    }

    async function hideResults() {
        if (!results.classList.contains('visible')) return Promise.resolve();
        results.classList.remove('visible');
        return new Promise(resolve => {
            const onTransitionEnd = () => { results.style.display = 'none'; results.removeEventListener('transitionend', onTransitionEnd); resolve(); };
            results.addEventListener('transitionend', onTransitionEnd, { once: true });
        });
    }

    async function showResults() {
        if (results.classList.contains('visible')) return Promise.resolve();
        results.style.display = 'block';
        results.offsetHeight;
        results.classList.add('visible');
        return Promise.resolve();
    }

    async function uploadImage(file) {
        showPreview(file);
        dropZone.classList.add('uploading');
        const wasVisible = results.classList.contains('visible');
        if (wasVisible) await hideResults();
        const formData = new FormData();
        formData.append('image', file);
        formData.append('top_k', maxTags.toString());
        try {
            const response = await fetch('/predict', { method: 'POST', body: formData });
            if (!response.ok) {
                let errorMsg = 'Server error. Please try again later.';
                try { const data = await response.json(); errorMsg = data.error || errorMsg; } catch (e) {}
                throw new Error(errorMsg);
            }
            const data = await response.json();
            if (data.success) {
                const baseTags = data.tags || [];
                const autoMeta = data.auto_meta || [];
                const merged = baseTags.slice();
                autoMeta.forEach(t => {
                    if (!merged.find(x => x.tag === t)) {
                        merged.push({ tag: t, prob: 1.0, category: 'Meta' });
                    }
                });
                allTags = merged;
                autoMetaTagSet = new Set(autoMeta);
                addedTags.clear();
                removedTags.clear();
                currentFormat = savedFormat;
                updateLocalFormatUI();
                displayTags(allTags);
                await showResults();
            } else showNotification(data.error || 'Failed to generate tags.', 'error');
        } catch (err) { showNotification(err.message || 'Network error. Please try again.', 'error'); }
        finally { dropZone.classList.remove('uploading'); }
    }

    function openHelpModal() {
        if (settingsMenu.classList.contains('show')) toggleSettings(false);
        helpModal.style.display = 'flex';
        document.body.classList.add('modal-open');
        requestAnimationFrame(() => helpModal.classList.add('show'));
    }

    function closeHelpModal() {
        helpModal.classList.remove('show');
        const cleanup = () => {
            if (!helpModal.classList.contains('show')) {
                helpModal.style.display = 'none';
                document.body.classList.remove('modal-open');
            }
            helpModal.removeEventListener('transitionend', cleanup);
        };
        helpModal.addEventListener('transitionend', cleanup, { once: true });
        setTimeout(() => {
            if (helpModal.style.display === 'flex') cleanup();
        }, 500);
    }

    function attachHammerTap(element, handler) {
        const hammer = new Hammer(element);
        hammer.on('tap', handler);
    }

    function initHammer() {
        attachHammerTap(dropZone, () => fileInput.click());
        attachHammerTap(eggContainer, () => {
            const isOpen = eggContainer.classList.contains('open');
            if (!isOpen) {
                const randomIndex = Math.floor(Math.random() * creaturePaths.length);
                eggCreature.src = creaturePaths[randomIndex];
            }
            eggContainer.classList.toggle('open');
        });
        attachHammerTap(settingsToggle, (e) => {
            settingsToggle.classList.add('pressed');
            setTimeout(() => {
                settingsToggle.classList.remove('pressed');
            }, 100);
            toggleSettings(!settingsMenu.classList.contains('show'));
        });
        attachHammerTap(closeSettings, () => toggleSettings(false));
        attachHammerTap(applyCustom, () => {
            const all = parseFloat(customAllInput.value);
            const conf = parseFloat(customConfidentInput.value);
            if (isNaN(all) || isNaN(conf) || all < 0 || all > 1 || conf < 0 || conf > 1) {
                showNotification('Please enter valid numbers between 0 and 1.', 'error');
                return;
            }
            allThreshold = all;
            confidentThreshold = conf;
            activePreset = 'custom';
            applyThresholds();
        });
        attachHammerTap(resetBtn, () => {
            allThreshold = 0.55; confidentThreshold = 0.75; savedFormat = 'e621';
            currentFormat = savedFormat; currentTheme = 'system'; activePreset = 'standard'; maxTags = 200;
            
            document.querySelectorAll('#themeToggle .theme-option').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.value === 'system');
            });
            document.querySelectorAll('#defaultFormatToggle .format-option').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.value === 'e621');
            });
            document.querySelectorAll('#maxTagsToggle .max-tag-option').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.value === '200');
            });
            
            updateTheme('system');
            applyThresholds();
            saveSettings();
        });

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

        document.querySelectorAll('#themeToggle .theme-option').forEach(btn => {
            attachHammerTap(btn, () => {
                document.querySelectorAll('#themeToggle .theme-option').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentTheme = btn.dataset.value;
                updateTheme(currentTheme);
                saveSettings();
            });
        });

        document.querySelectorAll('#defaultFormatToggle .format-option').forEach(btn => {
            attachHammerTap(btn, () => {
                document.querySelectorAll('#defaultFormatToggle .format-option').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                savedFormat = btn.dataset.value;
                currentFormat = savedFormat;
                saveSettings();
            });
        });

        document.querySelectorAll('#resultsFormatToggle .format-option').forEach(btn => {
            attachHammerTap(btn, () => {
                document.querySelectorAll('#resultsFormatToggle .format-option').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentFormat = btn.dataset.value;
            });
        });

        document.querySelectorAll('#maxTagsToggle .max-tag-option').forEach(btn => {
            attachHammerTap(btn, () => {
                document.querySelectorAll('#maxTagsToggle .max-tag-option').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                maxTags = parseInt(btn.dataset.value);
                saveSettings();
            });
        });
    }

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => dropZone.addEventListener(eventName, preventDefaults, false));
    ['dragenter', 'dragover'].forEach(eventName => dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false));
    ['dragleave', 'drop'].forEach(eventName => dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false));
    dropZone.addEventListener('drop', (e) => { const dt = e.dataTransfer; const files = dt.files; if (files.length) handleFiles(files); });
    fileInput.addEventListener('change', () => handleFiles(fileInput.files));
    document.addEventListener('paste', (e) => {
        const items = e.clipboardData?.items;
        if (!items) return;
        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            if (item.type.startsWith('image/')) {
                const file = item.getAsFile();
                if (file) { handleFiles([file]); e.preventDefault(); break; }
            }
        }
    });
    document.addEventListener('click', (e) => {
        if (currentPopup && !currentPopup.contains(e.target) && (!activePopupTagElement || !activePopupTagElement.contains(e.target))) closePopup();
        if (!settingsMenu.contains(e.target) && !settingsToggle.contains(e.target)) toggleSettings(false);
        if (helpModal && helpModal.style.display === 'flex') {
            const modalContent = helpModal.querySelector('.help-modal-content');
            if (e.target === helpModal || (helpModal.contains(e.target) && modalContent && !modalContent.contains(e.target))) closeHelpModal();
        }
    });
    window.addEventListener('resize', () => { 
        if (settingsMenu.classList.contains('show')) positionSettingsMenu(); 
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (helpModal && helpModal.style.display === 'flex') closeHelpModal();
            if (settingsMenu.classList.contains('show')) toggleSettings(false);
        }
    });

    if (helpBtn && helpModal) {
        helpBtn.addEventListener('click', (e) => { e.stopPropagation(); openHelpModal(); });
        if (closeHelpModalBtn) closeHelpModalBtn.addEventListener('click', closeHelpModal);
    }

    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.addEventListener('message', event => {
            if (event.data && event.data.action === 'offline') {
                showNotification('You are offline. Check your network connection.', 'info', 5000);
            }
        });
    }

    results.style.display = 'none';
    loadSettings();
    initHammer();
    setupGlobalCopyButton(copyGlobalConfident, () => confidentThreshold);
    setupGlobalCopyButton(copyGlobalAll, () => allThreshold);
});
