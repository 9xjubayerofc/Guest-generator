from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import os, zipfile, subprocess, shutil, json, time, io

app = Flask(__name__)
app.secret_key = "nayem_ultra_hosting_fixed"

UPLOAD_FOLDER = "uploads"
DB_FILE = "database.json"
DEFAULT_USER = "admin_root" # সব প্রজেক্ট এই ফোল্ডারে থাকবে

os.makedirs(os.path.join(UPLOAD_FOLDER, DEFAULT_USER), exist_ok=True)

processes = {}

def load_db():
    if not os.path.exists(DB_FILE):
        default = {"start_times": {}}
        with open(DB_FILE, "w") as f: json.dump(default, f)
        return default
    with open(DB_FILE, "r") as f:
        try:
            data = json.load(f)
            return data
        except:
            return {"start_times": {}}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- API ROUTES ---

@app.route("/")
def index():
    user_dir = os.path.join(UPLOAD_FOLDER, DEFAULT_USER)
    apps_list = []
    for name in os.listdir(user_dir):
        if os.path.isdir(os.path.join(user_dir, name)):
            p = processes.get((DEFAULT_USER, name))
            apps_list.append({"name": name, "running": (p and p.poll() is None)})
    return render_template("index.html", apps=apps_list)

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if file and file.filename.endswith(".zip"):
        app_name = file.filename.rsplit('.', 1)[0]
        user_dir = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, app_name)
        os.makedirs(user_dir, exist_ok=True)
        zip_path = os.path.join(user_dir, file.filename)
        file.save(zip_path)
        extract_dir = os.path.join(user_dir, "extracted")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        os.remove(zip_path)
    return redirect(url_for("index"))

@app.route("/run/<name>")
def run(name):
    app_dir = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, name)
    extract_dir = os.path.join(app_dir, "extracted")
    if (DEFAULT_USER, name) not in processes or processes[(DEFAULT_USER, name)].poll() is not None:
        main_file = next((f for f in ["main.py", "bot.py", "app.py", "index.js", "server.js"] if os.path.exists(os.path.join(extract_dir, f))), None)
        if main_file:
            log_path = os.path.join(app_dir, "logs.txt")
            log_file = open(log_path, "a")
            cmd = ["python", main_file] if main_file.endswith('.py') else ["node", main_file]
            processes[(DEFAULT_USER, name)] = subprocess.Popen(cmd, cwd=extract_dir, stdout=log_file, stderr=log_file, text=True)
            db = load_db()
            db["start_times"][name] = int(time.time() * 1000)
            save_db(db)
    return redirect(url_for("index"))

@app.route("/stop/<name>")
def stop(name):
    p = processes.get((DEFAULT_USER, name))
    if p: p.terminate(); del processes[(DEFAULT_USER, name)]
    db = load_db()
    if name in db.get("start_times", {}):
        del db["start_times"][name]
        save_db(db)
    return redirect(url_for("index"))

@app.route("/get_log/<name>")
def get_log(name):
    app_dir = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, name)
    log_path = os.path.join(app_dir, "logs.txt")
    log_content = ""
    if os.path.exists(log_path):
        with open(log_path, "r") as f: log_content = f.read()[-2000:]
    p = processes.get((DEFAULT_USER, name))
    db = load_db()
    is_running = (p and p.poll() is None)
    return jsonify({"log": log_content, "status": "RUNNING" if is_running else "OFFLINE", "start_time": db.get("start_times", {}).get(name, 0)})

@app.route("/search_json/<name>")
def search_json(name):
    extract_dir = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, name, "extracted")
    json_files = []
    if os.path.exists(extract_dir):
        for root, _, filenames in os.walk(extract_dir):
            for f in filenames:
                if f.endswith('.json'):
                    rel_path = os.path.relpath(os.path.join(root, f), extract_dir)
                    json_files.append({"name": f, "path": rel_path})
    return jsonify({"json_files": json_files})

@app.route("/download_file")
def download_specific_file():
    project = request.args.get('project')
    filename = request.args.get('filename')
    path = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, project, "extracted", filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "File not found", 404

@app.route("/list_files/<name>")
def list_files(name):
    extract_dir = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, name, "extracted")
    files = []
    if os.path.exists(extract_dir):
        for root, _, filenames in os.walk(extract_dir):
            for f in filenames:
                files.append(os.path.relpath(os.path.join(root, f), extract_dir))
    return jsonify({"files": files})

@app.route("/read_file", methods=["POST"])
def read_content():
    data = request.json
    path = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, data['project'], "extracted", data['filename'])
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return jsonify({"content": f.read()})
    return jsonify({"content": ""})

@app.route("/save_file", methods=["POST"])
def save_content():
    data = request.json
    path = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, data['project'], "extracted", data['filename'])
    with open(path, "w", encoding="utf-8") as f:
        f.write(data['content'])
    return jsonify({"status": "success"})

@app.route("/delete/<name>")
def delete(name):
    stop(name)
    app_dir = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, name)
    if os.path.exists(app_dir): shutil.rmtree(app_dir)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3522, debug=True)
