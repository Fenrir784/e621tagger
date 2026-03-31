# e621tagger

e621tagger is a web-based tool that automatically generates relevant tags for furry artwork using the **JTP-3 Hydra** model by Project RedRocket.

### **Can be accessed here: [tagger.fenrir784.ru](https://tagger.fenrir784.ru)**

### For usage tips click Need Help? in settings.

### Features:
- Mobile and desktop interface
- e621\PostyBirb tag formats
- PWA support
- Adjustable thresholds
- e621wiki lookups
- Self-host-able with all-in-one docker image

#### Have problems or suggestions? Contact me directly via [Telegram](https://t.me/fenrir784)

![alt text](https://github.com/Fenrir784/e621tagger/blob/latest/static/screenshots/preview.png?raw=true)
> ⚠️ **Note:** This repository contains the source code for the app. A live, fully functional instance is available at the link above.

---

## 🐳 Run with Docker (Self‑Hosted)
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
      - SAVE_UPLOADS=true          # optional, default is false
      - USE_PROXY=true             # optional, default is false, set to true for correct client IPs while using reverse proxy
      - GUNICORN_WORKERS=2         # optional, default is 1, amount of workers up, useful for redundancy  
      - GUNICORN_TIMEOUT=120       # optional, fefault is 120(seconds), timeout before worker tries to restart
    volumes:
      - ./uploads:/app/uploads     # where uploaded images are saved (if enabled)
    restart: unless-stopped
```
1. Save the file as `docker-compose.yml`.
2. Run `docker-compose up -d`.
3. Access the app at `http://localhost:5000`.

---

## 🧠 How It Works

- The backend uses **PyTorch** and the **JTP-3 Hydra** model, a fine‑tuned image classifier trained on e621 data.
- When you upload an image, it is resized, converted to patches, and fed through the model.
- The model outputs confidence scores for over 7,500 possible tags; the adjustable amount of tags from top 50 to 250 are returned.
- All processing happens on the server; no data is sent to third parties.

---

## 🛠️ Technology Stack

- **Backend:** Python, Flask, PyTorch, Gunicorn
- **Frontend:** Flask rendered HTML, CSS, JavaScript
- **Model:** [RedRocket/JTP-3](https://huggingface.co/RedRocket/JTP-3) on Hugging Face

---

## 📄 License

This project is licensed under the **Apache-2.0 license**. See the LICENSE file for details.

---

*Created by [fenrir784.ru](https://fenrir784.ru) – if you like the tool, consider dropping a star ⭐ on GitHub!*
