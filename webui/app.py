#!/usr/bin/env python3
from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename
import subprocess, time, uuid, pathlib, threading, os, signal

APP_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
UPLOAD_DIR = APP_DIR / 'uploads'
RESULT_DIR = APP_DIR / 'results'
LOG_DIR = APP_DIR / 'logs'
UPLOAD_DIR.mkdir(exist_ok=True)
RESULT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

WHISPER = PROJECT_ROOT / 'third_party' / 'whisper.cpp' / 'build' / 'bin' / 'whisper-cli'
MODEL = PROJECT_ROOT / 'third_party' / 'whisper.cpp' / 'models' / 'ggml-breeze-asr-26.bin'
ALLOWED = {'.wav', '.mp3', '.m4a', '.flac', '.ogg'}

app = Flask(__name__)
jobs = {}
lock = threading.Lock()

def tail_text(path, n=40):
    p = pathlib.Path(path)
    if not p.exists():
        return ''
    lines = p.read_text(errors='ignore').splitlines()
    return '\n'.join(lines[-n:])

@app.route('/')
def index():
    return render_template('index.html')

@app.post('/api/transcribe')
def transcribe():
    if not WHISPER.exists() or not MODEL.exists():
        return jsonify({'ok': False, 'error': '尚未安裝模型，先執行: bash scripts/install.sh'}), 400

    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': '請先選擇音檔'}), 400

    ext = pathlib.Path(f.filename).suffix.lower()
    if ext not in ALLOWED:
        return jsonify({'ok': False, 'error': f'不支援格式: {ext}'}), 400

    job_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    in_path = UPLOAD_DIR / f"{job_id}-{secure_filename(f.filename)}"
    out_base = RESULT_DIR / job_id
    log_path = LOG_DIR / f"{job_id}.log"
    f.save(in_path)

    cmd = [str(WHISPER), '-m', str(MODEL), '-f', str(in_path), '-otxt', '-of', str(out_base), '-nt']
    logf = open(log_path, 'w', encoding='utf-8')
    proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, text=True)

    with lock:
        jobs[job_id] = {
            'id': job_id, 'status': 'running', 'start_ts': time.time(), 'pid': proc.pid,
            'proc': proc, 'input_path': str(in_path), 'output_txt': str(out_base) + '.txt',
            'log_path': str(log_path), 'returncode': None,
        }
    return jsonify({'ok': True, 'job_id': job_id, 'status': 'running'})

@app.get('/api/jobs/<job_id>')
def job_status(job_id):
    with lock:
        j = jobs.get(job_id)
    if not j:
        return jsonify({'ok': False, 'error': 'job not found'}), 404

    rc = j['proc'].poll()
    if j['status'] == 'running' and rc is not None:
        j['status'] = 'done' if rc == 0 else 'failed'
        j['returncode'] = rc

    txt = ''
    if j['status'] == 'done' and pathlib.Path(j['output_txt']).exists():
        txt = pathlib.Path(j['output_txt']).read_text(errors='ignore').strip()

    return jsonify({
        'ok': True, 'job_id': job_id, 'status': j['status'],
        'elapsed_sec': round(time.time() - j['start_ts'], 2),
        'returncode': j['returncode'], 'pid': j['pid'],
        'input_path': j['input_path'], 'output_txt_path': j['output_txt'],
        'text': txt, 'log_tail': tail_text(j['log_path'], 50),
    })

@app.post('/api/jobs/<job_id>/cancel')
def job_cancel(job_id):
    with lock:
        j = jobs.get(job_id)
    if not j:
        return jsonify({'ok': False, 'error': 'job not found'}), 404
    if j['status'] != 'running':
        return jsonify({'ok': True, 'status': j['status']})
    try:
        os.kill(j['proc'].pid, signal.SIGTERM)
        j['status'] = 'cancelled'
        j['returncode'] = -15
        return jsonify({'ok': True, 'status': 'cancelled'})
    except ProcessLookupError:
        return jsonify({'ok': True, 'status': 'done'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '8013')))
