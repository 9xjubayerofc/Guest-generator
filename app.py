from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import os, zipfile, subprocess, shutil, json, time, io

app = Flask(__name__)

# Render বা পোর্টেবল এনভায়রনমেন্টের জন্য /tmp ব্যবহার
UPLOAD_FOLDER = "/tmp/uploads" 
DEFAULT_USER = "admin" 
os.makedirs(os.path.join(UPLOAD_FOLDER, DEFAULT_USER), exist_ok=True)

# প্রসেস স্টোর করার জন্য ডিকশনারি
processes = {}

def find_file(root_dir, target_name):
    for root, dirs, files in os.walk(root_dir):
        if target_name in files:
            return os.path.join(root, target_name)
    return None

@app.route("/")
def index():
    user_dir = os.path.join(UPLOAD_FOLDER, DEFAULT_USER)
    apps = []
    if os.path.exists(user_dir):
        for n in os.listdir(user_dir):
            if os.path.isdir(os.path.join(user_dir, n)):
                # প্রসেসটি সচল আছে কি না চেক করা
                proc = processes.get((DEFAULT_USER, n))
                running = (proc is not None and proc.poll() is None)
                apps.append({"name": n, "running": running})
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
    # মেইন ফাইল খোঁজা
    main = next((f for f in ["main.py", "bot.py", "app.py", "index.py"] if os.path.exists(os.path.join(ext, f))), None)
    
    if main:
        l_path = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, name, "logs.txt")
        # লগ ফাইল রিসেট
        with open(l_path, "w", encoding="utf-8") as f:
            f.write(f"--- Starting {main} ---\n")
        
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1" # পাইথন আউটপুট সরাসরি পাঠানোর জন্য
        
        # লগ ফাইল রাইট মোডে ওপেন রাখা
        log_file = open(l_path, "a", encoding="utf-8")
        
        # সাব-প্রসেস চালু করা
        processes[(DEFAULT_USER, name)] = subprocess.Popen(
            ["python3", "-u", main], 
            cwd=ext, 
            stdout=log_file, 
            stderr=log_file, 
            stdin=subprocess.PIPE, # ইনপুট নেয়ার জন্য জরুরি
            text=True,
            env=env,
            bufsize=1 # লাইন বাফারিং
        )
    return redirect(url_for("index"))

@app.route("/run_termux_cmd", methods=["POST"])
def cmd():
    data = request.json
    p_name = data.get('project')
    cmd_text = data.get('command')
    
    p = processes.get((DEFAULT_USER, p_name))
    if p and p.poll() is None:
        try:
            # ইনপুট পাঠানোর পর নিউলাইন যোগ করা এবং ফ্লাশ করা
            p.stdin.write(cmd_text + "\n")
            p.stdin.flush()
            return jsonify({"status": "sent"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    return jsonify({"status": "no_process"})

@app.route("/get_log/<name>")
def get_log(name):
    l_path = os.path.join(UPLOAD_FOLDER, DEFAULT_USER, name, "logs.txt")
    if os.path.exists(l_path):
        with open(l_path, "r", encoding="utf-8", errors="ignore") as f:
            log = f.read()[-10000:] # বড় ফাইল হলে শেষ অংশ দেখাবে
    else:
        log = "No logs found."
        
    proc = processes.get((DEFAULT_USER, name))
    running = (proc is not None and proc.poll() is None)
    return jsonify({"log": log, "status": "RUNNING" if running else "OFFLINE"})

@app.route("/stop/<name>")
def stop(name):
    p = processes.get((DEFAULT_USER, name))
    if p:
        p.terminate()
        try:
            p.wait(timeout=2)
        except:
            p.kill()
        del processes[(DEFAULT_USER, name)]
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3522))
    app.run(host="0.0.0.0", port=port, debug=False)
