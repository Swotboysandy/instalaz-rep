import os, threading
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, jsonify

from runner import (
    load_accounts, save_accounts, run_account, load_status,
    peek_caption, image_candidates, video_candidates,
    publish_selected_carousel, publish_selected_reel
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-key")

def background_run(acct):
    run_account(acct)

@app.route("/")
def index():
    accounts = load_accounts()
    for acct in accounts:
        acct["status"] = load_status(acct["state_prefix"])
    return render_template("index.html", accounts=accounts)

@app.route("/status")
def all_status():
    accounts = load_accounts()
    return jsonify([
        load_status(acct["state_prefix"])
        for acct in accounts
    ])

@app.route("/run/<int:idx>", methods=["POST"])
def run_now(idx):
    accounts = load_accounts()
    if not (0 <= idx < len(accounts)):
        return jsonify({"error": "Invalid account index"}), 400
    threading.Thread(target=background_run, args=(accounts[idx],), daemon=True).start()
    return jsonify({"status": "started"}), 202

# ─────────────────────────────────────────────────────
# Preview + Selective publish
# ─────────────────────────────────────────────────────
@app.get("/preview/<int:idx>")
def preview(idx):
    accounts = load_accounts()
    if not (0 <= idx < len(accounts)):
        return jsonify({"error": "Invalid account index"}), 400
    acct = accounts[idx]
    data = {"type": acct.get("type")}
    data["caption"] = peek_caption(acct)
    if acct.get("type") == "carousel":
        data["images"] = image_candidates(acct)  # pool to choose from
    else:
        data["videos"] = video_candidates(acct, k=8)
    return jsonify(data), 200

@app.post("/publish/<int:idx>")
def publish(idx):
    accounts = load_accounts()
    if not (0 <= idx < len(accounts)):
        return jsonify({"error": "Invalid account index"}), 400
    acct = accounts[idx]
    payload = request.get_json(silent=True) or {}
    try:
        if acct.get("type") == "carousel":
            selected = payload.get("images") or []
            caption  = payload.get("caption")
            res = publish_selected_carousel(acct, selected, caption=caption)
        else:
            video_url = payload.get("video")
            if not video_url:
                return jsonify({"error": "Missing 'video'"}), 400
            caption  = payload.get("caption")
            res = publish_selected_reel(acct, video_url, caption=caption)
        return jsonify({"ok": True, "result": res}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ─────────────────────────────────────────────────────
# Account form (create/edit)
# ─────────────────────────────────────────────────────
@app.route("/account/new", methods=["GET","POST"])
@app.route("/account/<int:idx>/edit", methods=["GET","POST"])
def account_form(idx=None):
    accounts = load_accounts()
    acct = accounts[idx] if idx is not None and 0 <= idx < len(accounts) else {}
    if request.method == "POST":
        data = {
            "name":             request.form["name"],
            "type":             request.form["type"],
            "access_token_env": request.form["access_token_env"],
            "ig_user_id_env":   request.form["ig_user_id_env"],
            "caption_url":      request.form["caption_url"],
            "state_prefix":     request.form["state_prefix"]
        }
        if data["type"] == "carousel":
            data["base_url"]        = request.form["base_url"]
            data["slides_per_post"] = int(request.form.get("slides_per_post") or 1)
            data.pop("video_base_url", None)
        else:
            data["video_base_url"]  = request.form["video_base_url"]
            data.pop("base_url", None)
            data.pop("slides_per_post", None)

        if acct and idx is not None:
            accounts[idx] = data
        else:
            accounts.append(data)

        save_accounts(accounts)
        return redirect(url_for("index"))

    return render_template("account_form.html", account=acct)

if __name__ == "__main__":
    app.run(debug=True)
