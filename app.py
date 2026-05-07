import os
import uuid
import glob
import json
import subprocess
import threading
import time
import sys
from flask import Flask, request, jsonify, send_file, render_template

YT_DLP_BIN = os.path.join(os.path.dirname(sys.executable), "yt-dlp")

app = Flask(__name__)
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

jobs = {}
last_heartbeat = time.time()


def run_download(job_id, url, format_choice, format_id, browser):
    job = jobs[job_id]
    out_template = os.path.join(DOWNLOAD_DIR, f"{job_id}.%(ext)s")

    cmd = [YT_DLP_BIN, "--no-playlist", "--remote-components", "ejs:github", "-o", out_template]
    
    if browser:
        cmd += ["--cookies-from-browser", browser]

    if format_choice == "audio":
        cmd += ["-x", "--audio-format", "mp3", "--embed-thumbnail"]
    elif format_id:
        cmd += ["-f", f"{format_id}+bestaudio/{format_id}/bestvideo+bestaudio/best", "--merge-output-format", "mp4"]
    else:
        cmd += ["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"]

    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            job["status"] = "error"
            job["error"] = result.stderr.strip().split("\n")[-1]
            return

        files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{job_id}.*"))
        if not files:
            job["status"] = "error"
            job["error"] = "Download completed but no file was found"
            return

        if format_choice == "audio":
            target = [f for f in files if f.endswith(".mp3")]
            chosen = target[0] if target else files[0]
        else:
            target = [f for f in files if f.endswith(".mp4")]
            chosen = target[0] if target else files[0]

        for f in files:
            if f != chosen:
                try:
                    os.remove(f)
                except OSError:
                    pass

        job["status"] = "done"
        job["file"] = chosen
        ext = os.path.splitext(chosen)[1]
        title = job.get("title", "").strip()
        prefix = job.get("prefix", "")
        # Sanitize title for filename
        if title:
            safe_title = "".join(c for c in title if c not in r'\/:*?"<>|').strip()[:60].strip()
            job["filename"] = f"{prefix}{safe_title}{ext}" if safe_title else f"{prefix}{os.path.basename(chosen)}"
        else:
            job["filename"] = f"{prefix}{os.path.basename(chosen)}"
    except subprocess.TimeoutExpired:
        job["status"] = "error"
        job["error"] = "Download timed out (5 min limit)"
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/extract-playlist", methods=["POST"])
def extract_playlist():
    data = request.json
    url = data.get("url", "").strip()
    browser = data.get("browser", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    cmd = [YT_DLP_BIN, "--flat-playlist", "--remote-components", "ejs:github", "-J", url]
    if browser:
        cmd += ["--cookies-from-browser", browser]
        
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return jsonify({"error": result.stderr.strip().split("\n")[-1]}), 400
            
        info = json.loads(result.stdout)
        if info.get("_type") == "playlist":
            entries = info.get("entries", [])
            urls = []
            for e in entries:
                if e.get("url"):
                    urls.append(e["url"])
                elif e.get("id"):
                    urls.append(f"https://www.youtube.com/watch?v={e['id']}")
            return jsonify({"is_playlist": True, "urls": urls, "title": info.get("title", "")})
        else:
            return jsonify({"is_playlist": False, "urls": [url]})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out parsing playlist"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/info", methods=["POST"])
def get_info():
    data = request.json
    url = data.get("url", "").strip()
    browser = data.get("browser", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    cmd = [YT_DLP_BIN, "--no-playlist", "--remote-components", "ejs:github", "-j", url]
    if browser:
        cmd += ["--cookies-from-browser", browser]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return jsonify({"error": result.stderr.strip().split("\n")[-1]}), 400

        info = json.loads(result.stdout)

        # Build quality options — keep best format per resolution
        best_by_height = {}
        for f in info.get("formats", []):
            height = f.get("height")
            if height and f.get("vcodec", "none") != "none":
                tbr = f.get("tbr") or 0
                if height not in best_by_height or tbr > (best_by_height[height].get("tbr") or 0):
                    best_by_height[height] = f

        formats = []
        for height, f in best_by_height.items():
            formats.append({
                "id": f["format_id"],
                "label": f"{height}p",
                "height": height,
            })
        formats.sort(key=lambda x: x["height"], reverse=True)

        return jsonify({
            "title": info.get("title", ""),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration"),
            "uploader": info.get("uploader", ""),
            "formats": formats,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out fetching video info"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.json
    url = data.get("url", "").strip()
    format_choice = data.get("format", "video")
    format_id = data.get("format_id")
    title = data.get("title", "")
    browser = data.get("browser", "").strip()
    file_prefix = data.get("file_prefix", "")

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    job_id = uuid.uuid4().hex[:10]
    jobs[job_id] = {"status": "downloading", "url": url, "title": title, "prefix": file_prefix}

    thread = threading.Thread(target=run_download, args=(job_id, url, format_choice, format_id, browser))
    thread.daemon = True
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def check_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "status": job["status"],
        "error": job.get("error"),
        "filename": job.get("filename"),
    })


@app.route("/api/file/<job_id>")
def download_file(job_id):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "File not ready"}), 404
    return send_file(job["file"], as_attachment=True, download_name=job["filename"])


@app.route("/api/heartbeat")
def heartbeat():
    global last_heartbeat
    last_heartbeat = time.time()
    return "OK"


@app.route("/api/zip", methods=["POST"])
def create_zip():
    data = request.json
    job_ids = data.get("job_ids", [])
    title = data.get("title", "ReClip_Playlist")
    import zipfile
    
    zip_filename = f"{uuid.uuid4().hex[:10]}.zip"
    zip_path = os.path.join(DOWNLOAD_DIR, zip_filename)
    
    try:
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for jid in job_ids:
                job = jobs.get(jid)
                if job and job.get("status") == "done" and job.get("file"):
                    if os.path.exists(job["file"]):
                        zipf.write(job["file"], arcname=job.get("filename", os.path.basename(job["file"])))
        return jsonify({"zip_id": zip_filename, "zip_name": f"{title}.zip"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/file-raw/<zip_id>")
def download_zip(zip_id):
    zip_path = os.path.join(DOWNLOAD_DIR, zip_id)
    download_name = request.args.get("name", "Playlist.zip")
    if not os.path.exists(zip_path):
        return jsonify({"error": "Zip not found"}), 404
    return send_file(zip_path, as_attachment=True, download_name=download_name)


def monitor_heartbeat():
    while True:
        time.sleep(5)
        if time.time() - last_heartbeat > 300:
            print("\n[Auto-Shutdown] No heartbeat detected for 5 minutes. Shutting down...")
            os._exit(0)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8899))
    host = os.environ.get("HOST", "127.0.0.1")

    # Start heartbeat monitor
    monitor_thread = threading.Thread(target=monitor_heartbeat, daemon=True)
    monitor_thread.start()

    app.run(host=host, port=port)
