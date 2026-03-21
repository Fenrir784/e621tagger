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
    const formatE621 = document.getElementById('formatE621');
    const formatPosty = document.getElementById('formatPosty');
    const settingsToggle = document.getElementById('settingsToggle');
    const settingsMenu = document.getElementById('settingsMenu');
    const closeSettings = document.getElementById('closeSettings');
    const presetBtns = document.querySelectorAll('.preset-btn');
    const customPresetBtn = document.getElementById('customPresetBtn');
    const customPanel = document.getElementById('customThresholdsPanel');
    const customAllInput = document.getElementById('customAll');
    const customConfidentInput = document.getElementById('customConfident');
    const applyCustom = document.getElementById('applyCustom');
    const formatOptions = document.querySelectorAll('.format-option');
    const resetBtn = document.getElementById('resetSettings');
    const themeOptions = document.querySelectorAll('.theme-option');
    const maxTagBtns = document.querySelectorAll('.max-tag-option');

    const eggContainer = document.getElementById('eggContainer');
    const eggCreature = document.getElementById('eggCreature');

    const MAX_FILE_SIZE = 20 * 1024 * 1024;
    const ALLOWED_MAX_TAGS = [50, 75, 100, 150, 200, 250];
    const LONG_PRESS_DURATION = 500;

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

    const ratingTags = new Set(['safe', 'questionable', 'explicit']);

    const creaturePaths = [
        '/static/f1.png',
        '/static/f2.png',
        '/static/f3.png',
        '/static/f4.png',
        '/static/f5.png',
        '/static/f6.png',
        '/static/f7.png',
        '/static/f8.png',
        '/static/f9.png'
    ];

    function preloadCreatures() {
        creaturePaths.forEach(path => {
            const img = new Image();
            img.src = path;
        });
    }
    preloadCreatures();

    eggContainer.addEventListener('click', () => {
        const isOpen = eggContainer.classList.contains('open');
        if (!isOpen) {
            const randomIndex = Math.floor(Math.random() * creaturePaths.length);
            eggCreature.src = creaturePaths[randomIndex];
        }
        eggContainer.classList.toggle('open');
    });

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
                updateTheme(currentTheme);
                updateLocalFormatUI();
                updateSettingsFormatUI();
                updateThresholdUI();
                updateMaxTagsUI();
            } catch (e) {
                console.warn('Failed to load settings', e);
            }
        } else {
            activePreset = 'standard';
            maxTags = 200;
            updateThresholdUI();
            updateMaxTagsUI();
        }
    }

    function saveSettings() {
        const settings = {
            allThreshold,
            confidentThreshold,
            defaultFormat: savedFormat,
            theme: currentTheme,
            activePreset,
            maxTags,
        };
        localStorage.setItem('e621tagger-settings', JSON.stringify(settings));
    }

    function updateMaxTagsUI() {
        maxTagBtns.forEach(btn => {
            const val = parseInt(btn.dataset.max);
            if (val === maxTags) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    function updateTheme(theme) {
        currentTheme = theme;
        document.body.classList.remove('theme-light', 'theme-dark');
        if (theme === 'light') {
            document.body.classList.add('theme-light');
        } else if (theme === 'dark') {
            document.body.classList.add('theme-dark');
        }
        themeOptions.forEach(opt => {
            if (opt.dataset.theme === theme) {
                opt.classList.add('active');
            } else {
                opt.classList.remove('active');
            }
        });
    }

    function updateLocalFormatUI() {
        if (currentFormat === 'e621') {
            formatE621.classList.add('active');
            formatPosty.classList.remove('active');
        } else {
            formatPosty.classList.add('active');
            formatE621.classList.remove('active');
        }
    }

    function updateSettingsFormatUI() {
        formatOptions.forEach(opt => {
            if (opt.dataset.format === savedFormat) {
                opt.classList.add('active');
            } else {
                opt.classList.remove('active');
            }
        });
    }

    function updateThresholdUI() {
        presetBtns.forEach(btn => {
            const preset = btn.dataset.preset;
            if (preset === activePreset) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        if (activePreset === 'custom') {
            customPanel.classList.add('open');
        } else {
            customPanel.classList.remove('open');
        }
        customAllInput.value = allThreshold.toFixed(2);
        customConfidentInput.value = confidentThreshold.toFixed(2);
    }

    function refreshTagClasses() {
        document.querySelectorAll('.tag').forEach(el => {
            const tagName = el.dataset.tag;
            const tagObj = allTags.find(t => t.tag === tagName);
            if (!tagObj) return;
            el.classList.remove('confident', 'all');
            if (tagObj.prob >= confidentThreshold) {
                el.classList.add('confident');
            } else if (tagObj.prob >= allThreshold) {
                el.classList.add('all');
            }
            el.classList.remove('added', 'removed');
            if (addedTags.has(tagName)) {
                el.classList.add('added');
            } else if (removedTags.has(tagName)) {
                el.classList.add('removed');
            }
        });
        updateCategoryButtonsDisabled();
    }

    function applyThresholds() {
        if (allTags.length > 0) {
            refreshTagClasses();
            setupCategoryCopyButtons();
        }
        updateThresholdUI();
        saveSettings();
    }

    presetBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const preset = btn.dataset.preset;
            if (preset === 'custom') {
                activePreset = 'custom';
                updateThresholdUI();
                saveSettings();
                return;
            }
            activePreset = preset;
            switch (preset) {
                case 'conservative':
                    allThreshold = 0.65;
                    confidentThreshold = 0.85;
                    break;
                case 'standard':
                    allThreshold = 0.55;
                    confidentThreshold = 0.75;
                    break;
                case 'liberal':
                    allThreshold = 0.45;
                    confidentThreshold = 0.65;
                    break;
            }
            customAllInput.value = allThreshold.toFixed(2);
            customConfidentInput.value = confidentThreshold.toFixed(2);
            applyThresholds();
        });
    });

    applyCustom.addEventListener('click', () => {
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

    formatOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            const format = opt.dataset.format;
            savedFormat = format;
            updateSettingsFormatUI();
            saveSettings();
        });
    });

    themeOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            const theme = opt.dataset.theme;
            updateTheme(theme);
            saveSettings();
        });
    });

    maxTagBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const val = parseInt(btn.dataset.max);
            if (ALLOWED_MAX_TAGS.includes(val)) {
                maxTags = val;
                updateMaxTagsUI();
                saveSettings();
            }
        });
    });

    resetBtn.addEventListener('click', () => {
        allThreshold = 0.55;
        confidentThreshold = 0.75;
        savedFormat = 'e621';
        currentFormat = savedFormat;
        currentTheme = 'system';
        activePreset = 'standard';
        maxTags = 200;
        updateTheme('system');
        updateLocalFormatUI();
        updateSettingsFormatUI();
        updateMaxTagsUI();
        applyThresholds();
        saveSettings();
    });

    function toggleSettings(show) {
        if (show) {
            settingsMenu.classList.add('show');
            settingsToggle.classList.add('open');
            positionSettingsMenu();
        } else {
            settingsMenu.classList.remove('show');
            settingsToggle.classList.remove('open');
        }
    }

    function positionSettingsMenu() {
        const toggleRect = settingsToggle.getBoundingClientRect();
        const containerRect = document.querySelector('.container').getBoundingClientRect();
        let left = toggleRect.left - containerRect.left;
        let top = toggleRect.bottom - containerRect.top + 5;
        settingsMenu.style.left = left + 'px';
        settingsMenu.style.top = top + 'px';
    }

    settingsToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleSettings(!settingsMenu.classList.contains('show'));
    });

    closeSettings.addEventListener('click', () => {
        toggleSettings(false);
    });

    document.addEventListener('click', (e) => {
        if (!settingsMenu.contains(e.target) && !settingsToggle.contains(e.target)) {
            toggleSettings(false);
        }
    });

    window.addEventListener('resize', () => {
        if (settingsMenu.classList.contains('show')) {
            positionSettingsMenu();
        }
    });

    formatE621.addEventListener('click', () => {
        currentFormat = 'e621';
        updateLocalFormatUI();
    });
    formatPosty.addEventListener('click', () => {
        currentFormat = 'posty';
        updateLocalFormatUI();
    });

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) handleFiles(files);
    });

    dropZone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', () => handleFiles(fileInput.files));

    document.addEventListener('paste', (e) => {
        const items = e.clipboardData?.items;
        if (!items) return;
        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            if (item.type.startsWith('image/')) {
                const file = item.getAsFile();
                if (file) {
                    handleFiles([file]);
                    e.preventDefault();
                    break;
                }
            }
        }
    });

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
        uploadImage(file);
    }

    function showPreview(file) {
        const existingImg = dropZone.querySelector('img');
        if (existingImg) existingImg.remove();
        uploadContent.style.display = 'none';
        const img = document.createElement('img');
        img.src = URL.createObjectURL(file);
        img.alt = 'Preview';
        img.style.opacity = '0';
        dropZone.appendChild(img);
        dropZone.classList.add('has-image');
        setTimeout(() => { img.style.opacity = '1'; }, 10);
    }

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
        if (wasVisible) {
            await hideResults();
        }

        const formData = new FormData();
        formData.append('image', file);
        formData.append('top_k', maxTags.toString());

        try {
            const response = await fetch('/predict', { method: 'POST', body: formData });
            if (!response.ok) {
                let errorMsg = 'Server error. Please try again later.';
                try {
                    const data = await response.json();
                    errorMsg = data.error || errorMsg;
                } catch (e) {
                }
                throw new Error(errorMsg);
            }
            const data = await response.json();
            if (data.success) {
                allTags = data.tags;
                addedTags.clear();
                removedTags.clear();
                currentFormat = savedFormat;
                updateLocalFormatUI();
                displayTags(allTags);
                await showResults();
            } else {
                showNotification(data.error || 'Failed to generate tags.', 'error');
            }
        } catch (err) {
            const errorMsg = err.message || 'Network error. Please try again.';
            showNotification(errorMsg, 'error');
        } finally {
            dropZone.classList.remove('uploading');
        }
    }

    function getTagCategory(prob) {
        if (prob >= confidentThreshold) return 'confident';
        if (prob >= allThreshold) return 'all';
        return 'low';
    }

    function isTagIncluded(tagObj, threshold) {
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

    const tagDescriptionCache = new Map();

    async function fetchTagDescription(tagName) {
        if (tagDescriptionCache.has(tagName)) {
            return tagDescriptionCache.get(tagName);
        }
        const url = `https://e621.net/wiki_pages.json?search[title]=${encodeURIComponent(tagName)}&limit=1`;
        try {
            const response = await fetch(url, {
                headers: {
                    'User-Agent': 'e621tagger/1.0 (https://tagger.fenrir784.ru)'
                }
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            if (data && data.length > 0) {
                const wiki = data[0];
                const result = {
                    exists: true,
                    title: wiki.title || tagName,
                    body: wiki.body || 'No description available.'
                };
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

    function parseDText(dtext) {
        if (!dtext) return '';

        let text = dtext;

        function removeBlockTags(tag, keepContent = true) {
            const openRegex = new RegExp(`\\[${tag}(?:=[^\\]]*)?\\]`, 'g');
            const closeRegex = new RegExp(`\\[\\/${tag}\\]`, 'g');
            if (keepContent) {
                while (true) {
                    let openMatch = openRegex.exec(text);
                    if (!openMatch) break;
                    let openIdx = openMatch.index;
                    let closeIdx = text.indexOf(`[/${tag}]`, openIdx);
                    if (closeIdx === -1) break;
                    let before = text.slice(0, openIdx);
                    let content = text.slice(openIdx + openMatch[0].length, closeIdx);
                    let after = text.slice(closeIdx + 3 + tag.length);
                    text = before + content + after;
                }
            } else {
                text = text.replace(new RegExp(`\\[${tag}(?:=[^\\]]*)?\\][\\s\\S]*?\\[\\/${tag}\\]`, 'g'), '');
            }
        }

        removeBlockTags('section', true);
        removeBlockTags('quote', true);

        text = text.replace(/\[table\][\s\S]*?\[\/table\]/g, (match) => {
            let inner = match.replace(/\[table\]|\[\/table\]/g, '')
                            .replace(/\[tr\]|\[\/tr\]/g, '')
                            .replace(/\[td\]|\[\/td\]/g, '')
                            .replace(/\[\/?th\]/g, '');
            return inner;
        });

        text = text.replace(/\[s\]([\s\S]*?)\[\/s\]/g, '$1');

        let lines = text.split('\n');
        let processedLines = [];

        for (let line of lines) {
            let trimmed = line;
            const headerMatch = trimmed.match(/^h([1-6])\.\s*(.*)$/);
            if (headerMatch) {
                trimmed = `<strong>${headerMatch[2]}</strong>`;
            } else {
                const bulletMatch = trimmed.match(/^(\*{1,3})\s+(.*)$/);
                if (bulletMatch) {
                    const stars = bulletMatch[1];
                    const content = bulletMatch[2];
                    const level = stars.length;
                    const bulletSymbol = level === 1 ? '•' : '·';
                    trimmed = `${bulletSymbol} ${content}`;
                }
            }
            processedLines.push(trimmed);
        }
        text = processedLines.join('\n');

        text = text.replace(/\[b\]([\s\S]*?)\[\/b\]/g, '<strong>$1</strong>');
        text = text.replace(/\[i\]([\s\S]*?)\[\/i\]/g, '<em>$1</em>');
        text = text.replace(/\[u\]([\s\S]*?)\[\/u\]/g, '<u>$1</u>');
        text = text.replace(/\[sup\]([\s\S]*?)\[\/sup\]/g, '<sup>$1</sup>');

        text = text.replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, (match, target, display) => {
            const href = `https://e621.net/wiki_pages?title=${encodeURIComponent(target)}`;
            return `<a href="${href}" target="_blank" rel="noopener noreferrer">${escapeHtml(display)}</a>`;
        });
        text = text.replace(/\[\[([^\]]+)\]\]/g, (match, p1) => {
            const href = `https://e621.net/wiki_pages?title=${encodeURIComponent(p1)}`;
            return `<a href="${href}" target="_blank" rel="noopener noreferrer">${escapeHtml(p1)}</a>`;
        });

        text = text.replace(/\n/g, '<br>');
        text = text.replace(/(<br>){3,}/g, '<br><br>');
        text = text.replace(/^(<br>)+/, '').replace(/(<br>)+$/, '');

        if (text.length > 4000) {
            text = text.slice(0, 4000) + '…';
        }

        return text;
    }

    function escapeHtml(unsafe) {
        if (!unsafe) return '';
        return unsafe.replace(/[&<>]/g, function(m) {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        });
    }

    let longPressTimer = null;
    let isLongPressTriggered = false;
    let currentPopup = null;

    function handleTagLongPress(tagObj, element) {
        if (isLongPressTriggered) return;
        isLongPressTriggered = true;
        showTagPopup(tagObj, element);
    }

    function closePopup() {
        if (currentPopup) {
            currentPopup.remove();
            currentPopup = null;
        }
        isLongPressTriggered = false;
        if (longPressTimer) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
    }

    function showTagPopup(tagObj, targetElement) {
        if (currentPopup) closePopup();

        const tagName = tagObj.tag;

        const popup = document.createElement('div');
        popup.className = 'tag-popup';

        const header = document.createElement('div');
        header.className = 'tag-popup-header';
        header.innerHTML = `<span class="tag-popup-title">${escapeHtml(tagName)}</span>
                            <button class="close-popup">✕</button>`;

        const content = document.createElement('div');
        content.className = 'tag-popup-content';
        content.innerHTML = '<div class="tag-popup-loading">Loading description...</div>';

        popup.appendChild(header);
        popup.appendChild(content);
        document.body.appendChild(popup);
        currentPopup = popup;

        const rect = targetElement.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        popup.style.visibility = 'hidden';
        popup.style.position = 'absolute';
        document.body.appendChild(popup);
        const popupRect = popup.getBoundingClientRect();
        popup.style.visibility = '';

        let top = rect.bottom + 8;
        let left = rect.left + (rect.width / 2) - (popupRect.width / 2);

        if (top + popupRect.height > viewportHeight - 10) {
            top = rect.top - popupRect.height - 8;
        }

        left = Math.max(10, Math.min(left, viewportWidth - popupRect.width - 10));

        popup.style.top = `${top + window.scrollY}px`;
        popup.style.left = `${left + window.scrollX}px`;

        const closeBtn = popup.querySelector('.close-popup');
        closeBtn.addEventListener('click', () => {
            closePopup();
        });

        fetchTagDescription(tagName).then(desc => {
            if (desc.exists) {
                const parsed = parseDText(desc.body);
                content.innerHTML = `<div class="tag-popup-text">${parsed}</div>`;
            } else {
                content.innerHTML = `<div class="tag-popup-error">${escapeHtml(desc.body)}</div>`;
            }
        }).catch(() => {
            content.innerHTML = '<div class="tag-popup-error">Failed to load description.</div>';
        });
    }

    function attachLongPressHandlers(element, tagObj) {
        let pressTimer = null;

        const startPress = (e) => {
            e.preventDefault();
            pressTimer = setTimeout(() => {
                handleTagLongPress(tagObj, element);
                element.removeEventListener('click', element._clickHandler);
                setTimeout(() => {
                    element.addEventListener('click', element._clickHandler);
                }, 100);
            }, LONG_PRESS_DURATION);
        };

        const cancelPress = () => {
            if (pressTimer) {
                clearTimeout(pressTimer);
                pressTimer = null;
            }
        };

        element.addEventListener('mousedown', startPress);
        element.addEventListener('mouseup', cancelPress);
        element.addEventListener('mouseleave', cancelPress);
        element.addEventListener('touchstart', startPress, { passive: false });
        element.addEventListener('touchend', cancelPress);
        element.addEventListener('touchcancel', cancelPress);
        element.addEventListener('contextmenu', (e) => e.preventDefault());
    }

    function handleTagClick(tagObj, element) {
        if (isLongPressTriggered) {
            isLongPressTriggered = false;
            return;
        }
        const tag = tagObj.tag;
        const prob = tagObj.prob;
        const category = getTagCategory(prob);

        const wasAdded = addedTags.has(tag);
        const wasRemoved = removedTags.has(tag);

        if (category === 'confident') {
            if (!wasAdded && !wasRemoved) {
                removedTags.add(tag);
            } else if (wasRemoved) {
                removedTags.delete(tag);
            } else if (wasAdded) {
                addedTags.delete(tag);
            }
        } else if (category === 'all') {
            if (!wasAdded && !wasRemoved) {
                addedTags.add(tag);
            } else if (wasAdded) {
                addedTags.delete(tag);
                removedTags.add(tag);
            } else if (wasRemoved) {
                removedTags.delete(tag);
            }
        } else {
            if (!wasAdded && !wasRemoved) {
                addedTags.add(tag);
            } else if (wasAdded) {
                addedTags.delete(tag);
            } else if (wasRemoved) {
                removedTags.delete(tag);
            }
        }

        document.querySelectorAll(`.tag[data-tag="${tag}"]`).forEach(el => {
            updateTagElement(el, tagObj);
        });

        updateCategoryButtonsDisabled();
    }

    function updateTagElement(el, tagObj) {
        el.classList.remove('added', 'removed');
        if (addedTags.has(tagObj.tag)) {
            el.classList.add('added');
        } else if (removedTags.has(tagObj.tag)) {
            el.classList.add('removed');
        }
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

    function displayTags(tags) {
        let rating = null;
        const nonRatingTags = [];
        tags.forEach(t => {
            if (ratingTags.has(t.tag)) {
                if (!rating || t.prob > rating.prob) {
                    rating = t;
                }
            } else {
                nonRatingTags.push(t);
            }
        });

        if (rating) {
            ratingDisplay.textContent = `Rating: ${rating.tag}`;
            ratingDisplay.className = 'rating-display ' + rating.tag;
            ratingDisplay.style.display = 'inline-block';
        } else {
            ratingDisplay.style.display = 'none';
        }

        const grouped = {};
        nonRatingTags.sort((a, b) => b.prob - a.prob);
        nonRatingTags.forEach(item => {
            const cat = item.category || 'Other';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(item);
        });

        const order = ['Copyright', 'Character', 'Species', 'Meta', 'General', 'Lore'];
        const sortedCategories = Object.keys(grouped).sort((a, b) => {
            const ia = order.indexOf(a);
            const ib = order.indexOf(b);
            if (ia !== -1 && ib !== -1) return ia - ib;
            if (ia !== -1) return -1;
            if (ib !== -1) return 1;
            return a.localeCompare(b);
        });

        categoriesContainer.innerHTML = '';
        sortedCategories.forEach(cat => {
            const catTags = grouped[cat];
            const catDiv = document.createElement('div');
            catDiv.className = 'category-block';

            const header = document.createElement('div');
            header.className = 'category-header';

            const categoryName = document.createElement('span');
            categoryName.className = 'category-name';
            categoryName.textContent = cat;

            const buttonsDiv = document.createElement('div');
            buttonsDiv.className = 'category-buttons';

            const confidentBtn = document.createElement('button');
            confidentBtn.className = 'cat-copy-btn confident';
            confidentBtn.dataset.category = cat;
            confidentBtn.dataset.type = 'confident';
            confidentBtn.title = 'Copy confident tags';
            confidentBtn.textContent = 'C';

            const allBtn = document.createElement('button');
            allBtn.className = 'cat-copy-btn all';
            allBtn.dataset.category = cat;
            allBtn.dataset.type = 'all';
            allBtn.title = 'Copy all tags';
            allBtn.textContent = 'A';

            const hasConfident = catTags.some(t => isTagIncluded(t, confidentThreshold));
            const hasAll = catTags.some(t => isTagIncluded(t, allThreshold));
            confidentBtn.disabled = !hasConfident;
            allBtn.disabled = !hasAll;

            buttonsDiv.appendChild(confidentBtn);
            buttonsDiv.appendChild(allBtn);

            header.appendChild(categoryName);
            header.appendChild(buttonsDiv);

            const tagsContainer = document.createElement('div');
            tagsContainer.className = 'category-tags';

            catTags.forEach(item => {
                const tagEl = document.createElement('span');
                tagEl.className = 'tag';
                tagEl.setAttribute('data-tag', item.tag);
                tagEl.textContent = item.tag;

                if (item.prob >= confidentThreshold) {
                    tagEl.classList.add('confident');
                } else if (item.prob >= allThreshold) {
                    tagEl.classList.add('all');
                }

                if (addedTags.has(item.tag)) {
                    tagEl.classList.add('added');
                } else if (removedTags.has(item.tag)) {
                    tagEl.classList.add('removed');
                }

                const clickHandler = (e) => {
                    e.stopPropagation();
                    handleTagClick(item, tagEl);
                };
                tagEl._clickHandler = clickHandler;
                tagEl.addEventListener('click', clickHandler);

                attachLongPressHandlers(tagEl, item);

                tagsContainer.appendChild(tagEl);
            });

            catDiv.appendChild(header);
            catDiv.appendChild(tagsContainer);
            categoriesContainer.appendChild(catDiv);
        });

        results.style.animation = 'fadeIn 0.3s ease';
        setupCategoryCopyButtons();
    }

    function showNotification(message, type = 'error', duration = 3000) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notificationContainer.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease forwards';
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, duration);
    }

    function formatTags(tags) {
        if (currentFormat === 'e621') {
            const grouped = {};
            tags.forEach(t => {
                const cat = t.category || 'Other';
                if (!grouped[cat]) grouped[cat] = [];
                grouped[cat].push(t.tag);
            });
            const order = ['Copyright', 'Character', 'Species', 'Meta', 'General', 'Lore'];
            const sortedCats = Object.keys(grouped).sort((a,b) => {
                const ia = order.indexOf(a);
                const ib = order.indexOf(b);
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

    function setupGlobalCopyButton(btn, getThreshold) {
        btn.addEventListener('click', async () => {
            const threshold = getThreshold();
            const filtered = filterTags(threshold);
            if (filtered.length === 0) {
                showNotification('No tags meet the threshold.', 'error');
                return;
            }
            const text = formatTags(filtered);
            await copyToClipboard(text, filtered.length, currentFormat, btn);
        });
    }

    function setupCategoryCopyButtons() {
        document.querySelectorAll('.cat-copy-btn').forEach(btn => {
            btn.removeEventListener('click', btn._handler);
            const category = btn.dataset.category;
            const type = btn.dataset.type;
            const threshold = type === 'confident' ? confidentThreshold : allThreshold;
            const handler = async () => {
                if (btn.disabled) return;
                const filtered = filterTagsByCategory(category, threshold);
                if (filtered.length === 0) {
                    showNotification(`No ${type} tags in ${category}.`, 'error');
                    return;
                }
                const text = formatTags(filtered);
                await copyToClipboard(text, filtered.length, currentFormat, btn);
            };
            btn._handler = handler;
            btn.addEventListener('click', handler);
        });
    }

    async function copyToClipboard(text, count, format, btn) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            try {
                await navigator.clipboard.writeText(text);
                showCopySuccess(btn, count, format);
            } catch {
                fallbackCopy(text, btn, count, format);
            }
        } else {
            fallbackCopy(text, btn, count, format);
        }
    }

    function showCopySuccess(btn, count, format) {
        if (btn._copyTimeout) clearTimeout(btn._copyTimeout);
        btn.classList.add('copied');
        const emoji = format === 'e621' ? '📋' : '🐦';
        const displayName = format === 'e621' ? 'e621' : 'PostyBirb';
        const message = `${emoji} Copied ${count} ${count === 1 ? 'tag' : 'tags'} • ${displayName}`;
        showNotification(message, 'success');
        btn._copyTimeout = setTimeout(() => {
            btn.classList.remove('copied');
        }, 1000);
    }

    function fallbackCopy(text, btn, count, format) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            if (document.execCommand('copy')) {
                showCopySuccess(btn, count, format);
            } else {
                showNotification('Unable to copy. Please copy manually.', 'error');
            }
        } catch {
            showNotification('Copy failed. Please copy manually.', 'error');
        }
        document.body.removeChild(textarea);
    }

    document.addEventListener('click', (e) => {
        if (currentPopup && !currentPopup.contains(e.target)) {
            closePopup();
        }
    });

    results.style.display = 'none';
    loadSettings();
    setupGlobalCopyButton(copyGlobalConfident, () => confidentThreshold);
    setupGlobalCopyButton(copyGlobalAll, () => allThreshold);
});
