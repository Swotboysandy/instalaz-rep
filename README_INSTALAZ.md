# INSTALAZ

**INSTALAZ** is a no-nonsense, production‑ready micro app for **previewing and publishing Instagram Carousels & Reels** via the Instagram Graph API. It ships with a clean Flask dashboard, safe state tracking, and a simple `runner.py` engine that handles upload, readiness polling, and final publishing. Use it locally, in a VM, or deploy to your favorite PaaS.

> **Why this exists**: Most “IG autoposters” hide complexity or hard‑code assumptions. INSTALAZ is explicit, auditable, and easy to extend—perfect as a white‑label asset for agencies and creators who need reliable scheduled or manual posting with full control.

---

## ✨ Features

- **Two content types**: `carousel` (multi‑image) & `reel` (video).
- **Preview before publish**: See next caption & candidate media, then choose exactly what to post.
- **One‑click manual publish** (REST endpoints provided).
- **Background run per account**: Fire & forget from the dashboard.
- **Caption rotation with persistence**: Round‑robin captions from remote `.txt` files.
- **Deterministic media picking**: Image/video indices advance safely; videos tracked to avoid re‑use.
- **Per‑account status JSON**: Human‑readable `*_status.json` with message + timestamps.
- **Clean separation**: The Flask UI (`app.py`) is thin; the engine (`runner.py`) does the heavy lifting.
- **Config‑driven**: Add/remove accounts in `accounts.json`—no code changes.
- **Environment‑only secrets**: Access tokens and IG User IDs are read from env vars, not the repo.

---

## 🧱 Architecture (at a glance)

```
accounts.json   ──► app.py (Flask UI) ──► runner.py (engine)
     │                                     │
     │                                     ├─ uploads media (images/reels)
     │                                     ├─ polls readiness
     └──► per-account env vars             └─ publishes + writes status/indices
```

Key state files (per account, where `prefix = state_prefix`):

```
{prefix}_status.json         # last run status, message, timestamp
{prefix}_caption.json        # {"last_index": N} for captions
{prefix}_image.json          # {"last_index": N} for images (carousel)
{prefix}_video_used.json     # {"used": ["vid (1).mp4", ...]} for reels
```

---

## 📦 What’s included (your repo)

- `app.py` – Flask web UI and REST endpoints
- `runner.py` – Core engine: next media, upload, publish, state
- `templates/index.html` – Dashboard UI
- `templates/account_form.html` – Create/Edit accounts
- `accounts.json` – Your accounts config (PLACEHOLDER‑ONLY for distribution)
- `requirements.txt` – Dependencies (example below)
- `README.md` – This file 😉

---

## 🚀 Quickstart

### 1) Create & activate a virtualenv

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 2) Install dependencies

Create a `requirements.txt` like this (or use the one in the repo):

```
Flask==3.0.3
python-dotenv==1.0.1
requests==2.32.3
```

Then install:

```bash
pip install -r requirements.txt
```

### 3) Prepare environment variables

Create a `.env` next to `app.py`. **Do not** commit real values.

```env
# Flask app
FLASK_SECRET_KEY=change-me

# Example account A (carousel)
EXAMPLE_A_TOKEN=EAAG...your_long_token...
EXAMPLE_A_IG_ID=1784...your_ig_user_id...

# Example account B (reel)
EXAMPLE_B_TOKEN=EAAG...another_token...
EXAMPLE_B_IG_ID=1784...another_user_id...
```

> You will reference these env names in `accounts.json` via `access_token_env` and `ig_user_id_env`—**never** put raw tokens/IDs inside JSON.

### 4) Create `accounts.json` (sanitized template)

```json
[
  {
    "name": "Brand A Carousel",
    "type": "carousel",
    "access_token_env": "EXAMPLE_A_TOKEN",
    "ig_user_id_env": "EXAMPLE_A_IG_ID",
    "caption_url": "https://example.com/captions.txt",
    "state_prefix": "brand_a",
    "base_url": "https://example.com/images",
    "slides_per_post": 5
  },
  {
    "name": "Brand B Reel",
    "type": "reel",
    "access_token_env": "EXAMPLE_B_TOKEN",
    "ig_user_id_env": "EXAMPLE_B_IG_ID",
    "caption_url": "https://example.com/captions.txt",
    "state_prefix": "brand_b",
    "video_base_url": "https://example.com/videos"
  }
]
```

**Fields**

- `name` – Label for the dashboard.
- `type` – `carousel` or `reel`.
- `access_token_env` – Env var name that holds your IG access token.
- `ig_user_id_env` – Env var name that holds your IG user ID.
- `caption_url` – Public URL to a `.txt` with one caption per line.
- `state_prefix` – Unique key for state files (`brand_b_status.json`, etc.).
- `base_url` – (Carousel) Public base URL for images.
- `slides_per_post` – (Carousel) Number of slides to include per post.
- `video_base_url` – (Reel) Public base URL for `vid.mp4` & `vid (n).mp4`.

> **Image naming**: `img (1).jpg`, `img (2).jpg`, ...  
> **Alt naming (Ruthless mode)**: `ram (1).jpg`, `ram (2).jpg`, ...  
> **Videos**: `vid.mp4`, `vid (1).mp4`, `vid (2).mp4`, ...

### 5) Run the app

```bash
python app.py
# Flask will start at http://127.0.0.1:5000
```

Open the dashboard in your browser.

---

## 🖥️ UI & Endpoints

### Dashboard

- `GET /` – Lists all accounts + current status
- `POST /run/<idx>` – Start a background run for the account at index `idx`

### Status & Preview API

- `GET /status` – Returns aggregated statuses for all accounts
- `GET /preview/<idx>` – Returns `{ type, caption, images[] }` for carousels **or** `{ type, caption, videos[] }` for reels

### Manual Publish API

- `POST /publish/<idx>` – Publish selected media manually

**For carousels**:
```json
{
  "images": [
    "https://example.com/images/img%20(1).jpg",
    "https://example.com/images/img%20(2).jpg",
    "https://example.com/images/img%20(3).jpg"
  ],
  "caption": "Optional custom caption"
}
```

**For reels**:
```json
{
  "video": "https://example.com/videos/vid%20(5).mp4",
  "caption": "Optional custom caption"
}
```

### Accounts UI

- `GET /account/new` – Create new `accounts.json` entry
- `GET /account/<idx>/edit` – Edit an existing entry

> The form dynamically shows `base_url` + `slides_per_post` for carousels, or `video_base_url` for reels.

---

## 🧠 How media & captions are chosen

- **Captions**: `runner.py` pulls your `caption_url`, splits by lines, and rotates using `{prefix}_caption.json`.
- **Carousel images**: Uses `{prefix}_image.json` to pick the next N images. Two patterns are supported:
  - `img (n).jpg` (default) if your `base_url` contains `"instimage"`
  - `ram (n).jpg` (alternate) otherwise
- **Reels**: Picks from `vid.mp4`, `vid (1).mp4`, … while avoiding ones listed in `{prefix}_video_used.json` (which is updated on publish).

---

## 🔐 Security & Privacy

- **Never commit tokens or IG IDs**: keep them only in `.env` or your platform’s secret manager.
- `accounts.json` must reference **env var names**, not raw secrets.
- Serve media (images/videos) over HTTPS for best reliability.
- Treat `*_status.json` as logs—don’t include sensitive data there.

---

## 🧪 Local testing tips

- Use throwaway/professional IG accounts.
- Start with a **single** account entry and test both preview & manual publish.
- Confirm your media URLs are publicly reachable (status code 200).
- Validate caption length & character set for your language/emoji usage.

---

## ☁️ Deployment Recipes

### Option A: Gunicorn (generic Linux host)

**Procfile** (if your platform uses it):
```
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

Run locally:
```bash
pip install gunicorn
PORT=5000 gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

### Option B: Docker

**Dockerfile**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

ENV PORT=8000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
```

Build & run:
```bash
docker build -t instalaz .
docker run -p 8000:8000 --env-file .env instalaz
```

### Env on PaaS

- Set `FLASK_SECRET_KEY`, `*_TOKEN`, `*_IG_ID` in your dashboard.
- Add a health check against `/` (GET).
- Ensure outbound HTTPS is allowed (Facebook Graph API).

---

## 🛠️ Troubleshooting

- **`Missing environment var ...`**  
  The env var in `accounts.json` doesn’t exist in your runtime. Define it in `.env` or your PaaS.

- **`Invalid account index` (400)**  
  You called `/run/<idx>` or `/publish/<idx>` with an out‑of‑range index. Check `/` or `accounts.json`.

- **`Failed to fetch caption_url ...`**  
  Your caption file is not reachable or not public. Make sure it returns `200` and plain text.

- **`Media container ... failed readiness`**  
  Readiness polling timed out. Media might be invalid, too large, or the API is throttled. Try smaller files, slower cadence, or confirm account permissions.

- **`media_publish error ...`**  
  Usually indicates permissions or invalid `creation_id`. Verify your IG account is properly connected and the token has the required scopes.

- **No videos left**  
  You exhausted the available `vid*.mp4` files. Upload more or clear `{prefix}_video_used.json` if you intentionally want to repost.

---

## 🧩 Extending INSTALAZ

- **Schedulers**: Wrap `/run/<idx>` in cron/Task Scheduler or add APScheduler/Celery.
- **Multi‑tenant**: Namespace `accounts.json` per client or mount separate volumes.
- **Custom naming**: Replace the `img/ram` and `vid` patterns in `runner.py`.
- **Caption rules**: Add filters (hashtags, languages) before upload.
- **Webhooks**: Push publish results to Slack/Discord via webhooks in `save_status`.

---

## 🔄 Data & State Files

All state files write to the working directory:

- `{prefix}_status.json` – `{"last_run": "...Z", "status": "success|error|running|never", "message": "..."}`
- `{prefix}_caption.json` – `{"last_index": N}`
- `{prefix}_image.json` – `{"last_index": N}`
- `{prefix}_video_used.json` – `{"used": ["vid (1).mp4", ...]}`

**Reset this state** by deleting the files for a given `prefix`.

---

## 📁 Suggested project layout

```
INSTALAZ/
├─ app.py
├─ runner.py
├─ templates/
│  ├─ index.html
│  └─ account_form.html
├─ accounts.json
├─ requirements.txt
├─ .env             # not committed
└─ README.md
```

---

## 🔏 License & Liability

This template is provided “as‑is.” You are responsible for complying with the Instagram Platform policies, content rights, and all local laws/regulations. Use at your own risk.

---

## ❤️ Name it, ship it

This project’s name is **INSTALAZ**—your lightweight, agency‑grade autoposter that doesn’t hide the knobs. Clone it, brand it, and go make the internet prettier (or funnier).

If you need a hand customizing INSTALAZ for your workflow, open an issue or drop a note in your docs for future contributors.
