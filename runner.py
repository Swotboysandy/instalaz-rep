#!/usr/bin/env python3
import os, json, random, requests
from time import sleep
from urllib.parse import quote
from datetime import datetime
from dotenv import load_dotenv
from typing import List, Tuple

# ─────────────────────────────────────────────────────
# BOOTSTRAP
# ─────────────────────────────────────────────────────
load_dotenv()

ACCOUNTS_FILE = "accounts.json"
STATUS_SUFFIX = "_status.json"

def status_path(prefix):
    return f"{prefix}{STATUS_SUFFIX}"

def save_status(prefix, status, message=""):
    data = {
        "last_run": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "status": status,
        "message": message
    }
    with open(status_path(prefix), "w") as f:
        json.dump(data, f, indent=2)

def load_status(prefix):
    p = status_path(prefix)
    return json.load(open(p)) if os.path.exists(p) else {"last_run": None, "status": "never", "message": ""}

# ─────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────
def _norm_base(url: str) -> str:
    """Strip trailing slash for consistent url building."""
    return (url or "").rstrip("/")

def _cfg_token_igid(cfg) -> Tuple[str, str]:
    """Fetch token and ig user id from env, with helpful errors."""
    tok_env = cfg.get("access_token_env")
    usr_env = cfg.get("ig_user_id_env")
    if not tok_env or not usr_env:
        raise RuntimeError("Config missing 'access_token_env' or 'ig_user_id_env'.")
    token = os.getenv(tok_env)
    ig_id = os.getenv(usr_env)
    if not token:
        raise RuntimeError(f"Missing environment var {tok_env}")
    if not ig_id:
        raise RuntimeError(f"Missing environment var {usr_env}")
    return token, ig_id

def fetch_lines(url):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return [l.strip() for l in r.text.splitlines() if l.strip()]
    except Exception as e:
        raise RuntimeError(f"Failed to fetch caption_url {url}: {e}")

def wait_until_ready(creation_id, token, max_attempts=20, delay=2):
    """
    Poll container until FINISHED or ERROR.
    IG returns fields like: status='FINISHED'|'ERROR' and/or status_code='FINISHED' etc.
    """
    for i in range(max_attempts):
        try:
            resp = requests.get(
                f"https://graph.facebook.com/v19.0/{creation_id}",
                params={"fields": "status_code,status", "access_token": token},
                timeout=15
            ).json()
        except Exception as e:
            print(f"⚠️  Poll attempt {i+1} failed: {e}")
            sleep(delay)
            continue

        status = (resp.get("status_code") or resp.get("status") or "").upper()
        print(f"🔍 Attempt {i+1}/{max_attempts} – {creation_id} => {resp}")
        if status == "FINISHED":
            return True
        if status == "ERROR":
            return False
        sleep(delay)
    return False

def fetch_permalink(media_id: str, token: str) -> str:
    """
    After media_publish returns a media_id, get a stable permalink for logging.
    """
    try:
        r = requests.get(
            f"https://graph.facebook.com/v19.0/{media_id}",
            params={"fields": "permalink", "access_token": token},
            timeout=15
        )
        r.raise_for_status()
        return r.json().get("permalink", "")
    except Exception as e:
        print(f"⚠️  Could not fetch permalink for media {media_id}: {e}")
        return ""

# ─────────────────────────────────────────────────────
# STATE HELPERS
# ─────────────────────────────────────────────────────
def load_last_index(prefix, key):
    fn = f"{prefix}_{key}.json"
    if not os.path.exists(fn): return 0
    return json.load(open(fn)).get("last_index", 0)

def save_last_index(prefix, key, idx):
    fn = f"{prefix}_{key}.json"
    with open(fn, "w") as f:
        json.dump({"last_index": idx}, f, indent=2)

def load_used_list(prefix):
    fn = f"{prefix}_video_used.json"
    if not os.path.exists(fn): return []
    return json.load(open(fn)).get("used", [])

def save_used_list(prefix, used):
    fn = f"{prefix}_video_used.json"
    with open(fn, "w") as f:
        json.dump({"used": used}, f, indent=2)

# ─────────────────────────────────────────────────────
# ACCOUNTS CONFIG
# ─────────────────────────────────────────────────────
def load_accounts(path=ACCOUNTS_FILE):
    return json.load(open(path))

def save_accounts(accounts, path=ACCOUNTS_FILE):
    with open(path, "w") as f:
        json.dump(accounts, f, indent=2)

# ─────────────────────────────────────────────────────
# MEDIA LOGIC (mutating auto-mode)
# ─────────────────────────────────────────────────────
def next_caption(cfg):
    lines = fetch_lines(cfg["caption_url"])
    if not lines:
        raise RuntimeError("Caption list is empty.")
    idx = load_last_index(cfg["state_prefix"], "caption")
    caption = lines[idx % len(lines)]
    save_last_index(cfg["state_prefix"], "caption", idx+1)
    return caption

def next_images(cfg):
    count = int(cfg.get("slides_per_post", 1))
    last  = load_last_index(cfg["state_prefix"], "image")
    base  = _norm_base(cfg.get("base_url", ""))
    if not base:
        raise RuntimeError("Missing base_url for carousel.")
    urls  = []
    for i in range(1, count+1):
        fn = f"img ({last+i}).jpg"
        urls.append(f"{base}/{quote(fn, safe='')}")
    save_last_index(cfg["state_prefix"], "image", last+count)
    return urls

def next_ruthless_images(cfg):
    count = int(cfg.get("slides_per_post", 3))
    last  = load_last_index(cfg["state_prefix"], "image")
    base  = _norm_base(cfg.get("base_url", ""))
    if not base:
        raise RuntimeError("Missing base_url for carousel.")
    urls  = []
    for i in range(1, count+1):
        fn = f"ram ({last+i}).jpg"
        urls.append(f"{base}/{quote(fn, safe='')}")
    save_last_index(cfg["state_prefix"], "image", last+count)
    return urls

def next_video(cfg):
    used = set(load_used_list(cfg["state_prefix"]))
    files = ["vid.mp4"] + [f"vid ({i}).mp4" for i in range(1,200)]
    unused = [v for v in files if v not in used]
    if not unused:
        return None
    pick = random.choice(unused)
    used.add(pick)
    save_used_list(cfg["state_prefix"], list(used))
    base = _norm_base(cfg.get("video_base_url", ""))
    if not base:
        raise RuntimeError("Missing video_base_url for reel.")
    return f"{base}/{quote(pick, safe='')}"

# ─────────────────────────────────────────────────────
# UPLOAD / PUBLISH (base)
# ─────────────────────────────────────────────────────
def upload_image(url, cfg):
    token, ig_id = _cfg_token_igid(cfg)
    try:
        r = requests.post(
            f"https://graph.facebook.com/v19.0/{ig_id}/media",
            data={"image_url": url, "is_carousel_item":"true", "access_token": token},
            timeout=45
        )
        r.raise_for_status()
        return r.json()["id"]
    except Exception as e:
        raise RuntimeError(f"upload_image failed for {url}: {e}")

def upload_reel(url, cfg, caption: str):
    token, ig_id = _cfg_token_igid(cfg)
    try:
        r = requests.post(
            f"https://graph.facebook.com/v19.0/{ig_id}/media",
            data={"media_type":"REELS","video_url":url,"caption":caption,"access_token":token},
            timeout=90
        )
        r.raise_for_status()
        return r.json()["id"]
    except Exception as e:
        raise RuntimeError(f"upload_reel failed for {url}: {e}")

def create_carousel(child_ids: List[str], caption: str, cfg):
    token, ig_id = _cfg_token_igid(cfg)
    r = requests.post(
        f"https://graph.facebook.com/v19.0/{ig_id}/media",
        data={"media_type":"CAROUSEL","children":",".join(child_ids),"caption":caption,"access_token":token},
        timeout=45
    ).json()
    cid = r.get("id")
    if not cid:
        raise RuntimeError(f"Carousel container creation error: {r}")
    return cid, token

def publish_creation(creation_id: str, cfg):
    token, ig_id = _cfg_token_igid(cfg)
    pub = requests.post(
        f"https://graph.facebook.com/v19.0/{ig_id}/media_publish",
        data={"creation_id":creation_id,"access_token":token},
        timeout=45
    ).json()
    media_id = pub.get("id")
    if not media_id:
        raise RuntimeError(f"media_publish error: {pub}")
    return media_id, token

# ─────────────────────────────────────────────────────
# SINGLE ACCOUNT RUNNER (auto mode)
# ─────────────────────────────────────────────────────
def run_account(cfg):
    prefix = cfg["state_prefix"]
    save_status(prefix, "running", "")
    try:
        if cfg["type"] == "carousel":
            imgs = next_images(cfg) if "instimage" in (cfg.get("base_url") or "") else next_ruthless_images(cfg)
            child_ids  = []
            for u in imgs:
                cid = upload_image(u, cfg)
                token, _ = _cfg_token_igid(cfg)
                if wait_until_ready(cid, token):
                    child_ids.append(cid)
                else:
                    raise RuntimeError(f"Media container {cid} failed readiness.")
            cap = next_caption(cfg)
            creation_id, token = create_carousel(child_ids, cap, cfg)
            media_id, token = publish_creation(creation_id, cfg)
            permalink = fetch_permalink(media_id, token)
            msg = f"Carousel published ✅\nMedia ID: {media_id}\nPermalink: {permalink or '(not available)'}"
            save_status(prefix, "success", msg)
            print(f"✅ {cfg['name']}: {msg}")
            return {"media_id": media_id, "permalink": permalink}

        else:
            vid_cand = next_video(cfg)
            if not vid_cand:
                raise RuntimeError("No videos left")
            cap = next_caption(cfg)
            creation_id = upload_reel(vid_cand, cfg, cap)
            token, _ = _cfg_token_igid(cfg)
            if not wait_until_ready(creation_id, token):
                raise RuntimeError(f"Reel container {creation_id} failed readiness.")
            media_id, token = publish_creation(creation_id, cfg)
            permalink = fetch_permalink(media_id, token)
            msg = f"Reel published ✅\nMedia ID: {media_id}\nPermalink: {permalink or '(not available)'}"
            save_status(prefix, "success", msg)
            print(f"✅ {cfg['name']}: {msg}")
            return {"media_id": media_id, "permalink": permalink}

    except Exception as e:
        save_status(prefix, "error", str(e))
        print(f"✘ {cfg.get('name','(account)')} error: {e}")
        return None

# ─────────────────────────────────────────────────────
# PREVIEW (non-mutating) + SELECTIVE PUBLISH
# ─────────────────────────────────────────────────────
def peek_caption(cfg):
    lines = fetch_lines(cfg["caption_url"])
    idx = load_last_index(cfg["state_prefix"], "caption")
    return lines[idx % len(lines)] if lines else ""

def image_candidates(cfg, count=None) -> List[str]:
    if cfg.get("type") != "carousel":
        return []
    count = int(count or cfg.get("slides_per_post", 1))
    last  = load_last_index(cfg["state_prefix"], "image")
    base  = _norm_base(cfg.get("base_url", ""))
    ruthless = "instimage" not in (cfg.get("base_url") or "")
    pattern = "ram ({})" if ruthless else "img ({})"
    urls  = []
    for i in range(1, count + 4):
        fn = f"{pattern.format(last+i)}.jpg"
        urls.append(f"{base}/{quote(fn, safe='')}")
    return urls

def video_candidates(cfg, k=8) -> List[str]:
    if cfg.get("type") != "reel":
        return []
    used = set(load_used_list(cfg["state_prefix"]))
    files = ["vid.mp4"] + [f"vid ({i}).mp4" for i in range(1,200)]
    unused = [v for v in files if v not in used]
    cand = unused[:k]
    base = _norm_base(cfg.get("video_base_url", ""))
    return [f"{base}/{quote(v, safe='')}" for v in cand] if base else []

def advance_image_index(cfg, count_used):
    last = load_last_index(cfg["state_prefix"], "image")
    save_last_index(cfg["state_prefix"], "image", last + int(count_used))

def mark_video_used(cfg, selected_filename):
    used = set(load_used_list(cfg["state_prefix"]))
    fname = selected_filename.split("/")[-1]
    used.add(fname)
    save_used_list(cfg["state_prefix"], list(used))

def peek_then_commit_caption(cfg):
    lines = fetch_lines(cfg["caption_url"])
    idx = load_last_index(cfg["state_prefix"], "caption")
    cap = lines[idx % len(lines)] if lines else ""
    save_last_index(cfg["state_prefix"], "caption", idx+1)
    return cap

def publish_selected_carousel(cfg, selected_urls, caption=None):
    if not selected_urls:
        raise RuntimeError("No slides selected")
    token, ig_id = _cfg_token_igid(cfg)

    child_ids = []
    for u in selected_urls:
        r = requests.post(
            f"https://graph.facebook.com/v19.0/{ig_id}/media",
            data={"image_url": u, "is_carousel_item":"true", "access_token": token},
            timeout=45
        )
        r.raise_for_status()
        cid = r.json()["id"]
        if not wait_until_ready(cid, token):
            raise RuntimeError(f"Media {cid} failed readiness.")
        child_ids.append(cid)

    cap = caption or peek_then_commit_caption(cfg)
    creation_id, token = create_carousel(child_ids, cap, cfg)
    media_id, token = publish_creation(creation_id, cfg)
    permalink = fetch_permalink(media_id, token)

    advance_image_index(cfg, len(selected_urls))

    msg = f"Carousel (manual) published ✅\nMedia ID: {media_id}\nPermalink: {permalink or '(not available)'}"
    save_status(cfg["state_prefix"], "success", msg)
    print(f"✅ {cfg['name']}: {msg}")
    return {"media_id": media_id, "permalink": permalink}

def publish_selected_reel(cfg, selected_video_url, caption=None):
    token, _ = _cfg_token_igid(cfg)
    cap   = caption or peek_then_commit_caption(cfg)

    r = requests.post(
        f"https://graph.facebook.com/v19.0/{os.getenv(cfg['ig_user_id_env'])}/media",
        data={"media_type":"REELS","video_url":selected_video_url,"caption":cap,"access_token":token},
        timeout=90
    )
    r.raise_for_status()
    creation_id = r.json()["id"]

    if not wait_until_ready(creation_id, token):
        raise RuntimeError(f"Reel container {creation_id} failed readiness.")

    media_id, token = publish_creation(creation_id, cfg)
    permalink = fetch_permalink(media_id, token)
    mark_video_used(cfg, selected_video_url)

    msg = f"Reel (manual) published ✅\nMedia ID: {media_id}\nPermalink: {permalink or '(not available)'}"
    save_status(cfg["state_prefix"], "success", msg)
    print(f"✅ {cfg['name']}: {msg}")
    return {"media_id": media_id, "permalink": permalink}

# ─────────────────────────────────────────────────────
# CLI ENTRY
# ─────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        accounts = load_accounts()
    except Exception as e:
        print(f"✘ Failed to load {ACCOUNTS_FILE}: {e}")
        raise

    for a in accounts:
        print(f"\n→ {a.get('name','(unnamed)')} [{a.get('type')}]")
        run_account(a)

    print("\nAll finished.")
