# e621tagger
**Can be accessed here: [tagger.fenrir784.ru](https://tagger.fenrir784.ru)**

e621tagger is a web-based tool that automatically generates relevant tags for furry artwork using the **JTP-3 Hydra** model by Project RedRocket. It runs in your browser with a backend and provides a clean, responsive interface for copying tags in formats suitable for e621 and PostyBirb.
![alt text](https://github.com/Fenrir784/e621tagger/blob/latest/preview.jpg?raw=true)
> ⚠️ **Note:** This repository contains the source code for the application. A live, fully functional instance is already available at the link above.

---

## ✨ Features

- **Automatic Tagging** – Upload an image and get up to 250 relevant e621 tags, complete with confidence scores.
- **Two Copy Formats** – Copy tags in **e621** (space‑separated) or **PostyBirb** (comma‑separated) format with one click.
- **Threshold Presets & Custom Values** – Choose between Conservative, Standard, Liberal presets or set your own confidence thresholds for “All” and “Confident” tags.
- **Manual Tag Overrides** – Click any tag to force‑include (green) or exclude (red) it from copying, overriding the automatic thresholds.
- **Category Grouping** – Tags are grouped into categories like *Copyright, Character, Species, Meta, General, Lore* for easier browsing.
- **Theme Support** – Automatically follows your system theme (dark/light) with a manual override in settings.
- **Drag & Drop / Paste** – Drop an image anywhere on the page or paste from clipboard (Ctrl+V).
- **PWA Ready** – Install as a standalone app on mobile and desktop; works offline after first visit.
- **Smooth Animations** – Polished transitions for loading, showing/hiding results, and interacting with tags.

---

## 🚀 How to Use

1. Go to **[tagger.fenrir784.ru](https://tagger.fenrir784.ru)**.
2. Drag & drop an image onto the drop zone, or click to select a file (supports PNG, JPG, GIF, WebP, BMP, TIFF, max 20 MB).
3. Wait a moment – the image is processed locally on the server (CPU‑based, usually under 2 seconds).
4. Browse the generated tags, grouped by category.
   - **Confident** tags (≥ 0.75 by default) are highlighted in purple.
   - **All** tags (≥ 0.55 by default) are shown in muted blue.
   - Tags below the threshold appear dimmed.
5. Click any tag to manually include (green) or exclude (red) it from copying.
6. Use the buttons to copy:
   - **Copy Confident Tags** / **Copy All Tags** – copies all tags of that level in the currently selected format.
   - Within each category, small **C** and **A** buttons copy only tags from that category.
7. Adjust thresholds or default format via the **⚙️ Settings** menu in the top‑left corner.
   - Choose a preset or enter custom thresholds.
   - Pick your preferred default format (e621 / PostyBirb) – this will be used for future uploads.

---

## 🐳 Run with Docker (Self‑Hosted)

If you prefer to host your own instance, you can use the provided `docker-compose.yml`.

### Example `docker-compose.yml`

```yaml
services:
  e621tagger:
    image: ghcr.io/fenrir784/e621tagger:latest
    container_name: e621tagger
    ports:
      - "5000:5000"
    environment:
      - TZ=Europe/Moscow           # optional, adjust to your timezone
      - SAVE_UPLOADS=true           # set to false to disable file saving
    volumes:
      - ./uploads:/app/uploads      # where uploaded images are saved (if enabled)
    restart: unless-stopped
```
1. Save the file as `docker-compose.yml`.
2. Run `docker-compose up -d`.
3. Access the app at `http://localhost:5000`.

---

## 🧠 How It Works

- The backend uses **PyTorch** and the **JTP-3 Hydra** model, a fine‑tuned image classifier trained on e621 data.
- When you upload an image, it is resized, converted to patches, and fed through the model.
- The model outputs confidence scores for over 7,500 possible tags; the top 250 are returned.
- All processing happens on the server; no data is sent to third parties.

---

## 🛠️ Technology Stack

- **Backend:** Python, Flask, PyTorch, Gunicorn
- **Frontend:** HTML, CSS, JavaScript
- **Model:** [RedRocket/JTP-3](https://huggingface.co/RedRocket/JTP-3) on Hugging Face

---

## 📄 License

This project is licensed under the **MIT License**. See the LICENSE file for details.

---

*Created by [fenrir784.ru](https://fenrir784.ru) – if you like the tool, consider dropping a star ⭐ on GitHub!*
