from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import os, zipfile, subprocess, shutil, json, time, io

app = Flask(__name__)

UPLOAD_FOLDER = "/tmp/uploads" # রেন্ডারের জন্য /tmp ফোল্ডার ব্যবহার করা নিরাপদ
DEFAULT_USER = "admin" 
os.makedirs(os.path.join(UPLOAD_FOLDER, DEFAULT_USER), exist_ok=True)

processes = {}

def find_file(root_dir, target_name):
    for root, dirs, files in os.walk(root_dir):
        if target_name in files:
            return os.path.join(root, target_name)
    return None

@app.route("/")
def index():
    user_dir = os.path.join(UPLOAD_FOLDER, DEFAULT_USER)
    apps = [{"name": n, "running": (processes.get((DEFAULT_USER, n)) and processes[(DEFAULT_USER, n)].poll() is None)} for n in os.listdir(user_dir) if os.path.isdir(os.path.join(user_dir, n))]
    return render_template("index.html", apps=apps)

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if file and file.filename.endswith(".zip"):
        name = file.filename.rsplit('.', 1)[0]
        path = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, name)
        os.makedirs(path, exist_ok=True)
        ext = os.path.join(path, "extracted")
        if os.path.exists(ext): shutil.rmtree(ext)
        z_path = os.path.join(path, file.filename)
        file.save(z_path)
        with zipfile.ZipFile(z_path, 'r') as z: z.extractall(ext)
        os.remove(z_path)
    return redirect(url_for("index"))

@app.route("/run/<name>")
def run(name):
    ext = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, name, "extracted")
    main = next((f for f in ["main.py", "bot.py", "app.py"] if os.path.exists(os.path.join(ext, f))), None)
    if main:
        l_path = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, name, "logs.txt")
        open(l_path, "w").close()
        f = open(l_path, "a", encoding="utf-8")
        # -u flag and python path optimization
        processes[(DEFAULT_USER, name)] = subprocess.Popen(
            ["python3", "-u", main], cwd=ext, stdout=f, stderr=f, 
            stdin=subprocess.PIPE, text=True, bufsize=1
        )
    return redirect(url_for("index"))

@app.route("/run_termux_cmd", methods=["POST"])
def cmd():
    data = request.json
    p = processes.get((DEFAULT_USER, data['project']))
    if p and p.poll() is None:
        p.stdin.write(data['command'] + "\n")
        p.stdin.flush()
        return jsonify({"status": "sent"})
    return jsonify({"status": "no_process"})

@app.route("/get_log/<name>")
def get_log(name):
    l_path = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, name, "logs.txt")
    log = open(l_path, "r", errors="ignore").read()[-5000:] if os.path.exists(l_path) else "Initializing..."
    running = (processes.get((DEFAULT_USER, name)) and processes[(DEFAULT_USER, name)].poll() is None)
    return jsonify({"log": log, "status": "RUNNING" if running else "OFFLINE"})

@app.route("/stop/<name>")
def stop(name):
    p = processes.get((DEFAULT_USER, name))
    if p: p.terminate(); del processes[(DEFAULT_USER, name)]
    return redirect(url_for("index"))

@app.route("/search_and_download", methods=["POST"])
def search_and_download():
    data = request.json
    p_name, f_name = data.get('project'), data.get('filename')
    project_path = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, p_name, "extracted")
    file_path = find_file(project_path, f_name)
    if file_path:
        return jsonify({"status": "found", "url": f"/direct_download/{p_name}/{f_name}"})
    return jsonify({"status": "not_found"})

@app.route("/direct_download/<p_name>/<f_name>")
def direct_download(p_name, f_name):
    project_path = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, p_name, "extracted")
    file_path = find_file(project_path, f_name)
    if file_path: return send_file(file_path, as_attachment=True)
    return "File not found!", 404

# Health check route for Render
@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    # Render requires port from environment variable
    port = int(os.environ.get("PORT", 3522))
    app.run(host="0.0.0.0", port=port)
