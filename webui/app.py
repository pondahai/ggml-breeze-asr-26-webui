#!/usr/bin/env python3
from flask import Flask, request, render_template, jsonify, send_file, Response, stream_with_context
from werkzeug.utils import secure_filename
import subprocess, time, uuid, pathlib, threading, os, signal, json, requests

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

def ensure_wav(in_path: pathlib.Path, wav_path: pathlib.Path):
    if in_path.suffix.lower() == '.wav':
        return in_path
    cmd = ['ffmpeg', '-y', '-i', str(in_path), '-ac', '1', '-ar', '16000', str(wav_path)]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0 or not wav_path.exists():
        raise RuntimeError('ffmpeg convert failed: ' + (p.stderr or p.stdout)[-500:])
    return wav_path

@app.route('/')
def index():
    return render_template('index.html')

@app.post('/api/transcribe')
def transcribe():
    if not WHISPER.exists() or not MODEL.exists():
        return jsonify({'ok': False, 'error': '尚未安裝模型，先執行: bash scripts/install.sh'}), 400
    f = request.files.get('file')
    fmt = request.form.get('format', 'txt')
    max_len = request.form.get('max_len', '20')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': '請先選擇音檔'}), 400
    ext = pathlib.Path(f.filename).suffix.lower()
    if ext not in ALLOWED:
        return jsonify({'ok': False, 'error': f'不支援格式: {ext}'}), 400

    job_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    in_path = UPLOAD_DIR / f"{job_id}-{secure_filename(f.filename)}"
    wav_path = UPLOAD_DIR / f"{job_id}.wav"
    out_base = RESULT_DIR / job_id
    log_path = LOG_DIR / f"{job_id}.log"
    f.save(in_path)

    try:
        audio_path = ensure_wav(in_path, wav_path)
    except Exception as e:
        return jsonify({'ok': False, 'error': f'音檔轉檔失敗: {e}'}), 400

    cmd = [str(WHISPER), '-m', str(MODEL), '-f', str(audio_path), '-of', str(out_base), '-nt']
    cmd.extend(['-l', 'zh', '-ml', str(max_len), '-sow'])
    cmd.append('-otxt')
    if fmt == 'srt': cmd.append('-osrt')
    if fmt == 'vtt': cmd.append('-ovtt')

    logf = open(log_path, 'w', encoding='utf-8')
    proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, text=True)

    with lock:
        jobs[job_id] = {
            'id': job_id, 'status': 'running', 'start_ts': time.time(), 'pid': proc.pid,
            'proc': proc, 'input_path': str(in_path), 'audio_path': str(audio_path),
            'output_base': str(out_base), 'log_path': str(log_path), 'returncode': None,
            'requested_format': fmt
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
        main_output = pathlib.Path(j['output_base'] + '.' + j['requested_format'])
        j['status'] = 'done' if (rc == 0 and main_output.exists()) else 'failed'
        j['returncode'] = rc

    txt = ''
    main_output = pathlib.Path(j['output_base'] + '.' + j['requested_format'])
    if j['status'] == 'done' and main_output.exists():
        txt = main_output.read_text(errors='ignore').strip()

    return jsonify({
        'ok': True, 'job_id': job_id, 'status': j['status'],
        'elapsed_sec': round(time.time() - j['start_ts'], 2),
        'returncode': j['returncode'], 'pid': j['pid'],
        'input_path': j['input_path'], 'audio_path': j.get('audio_path'),
        'text': txt, 'log_tail': tail_text(j['log_path'], 50),
    })

@app.get('/api/jobs/<job_id>/download')
def job_download(job_id):
    with lock:
        j = jobs.get(job_id)
    if not j or j['status'] != 'done':
        return 'Not found or not ready', 404

    ext = request.args.get('ext', 'txt')
    target = pathlib.Path(j['output_base'] + '.' + ext)
    if not target.exists():
        return f'Format {ext} not available', 404

    return send_file(target, as_attachment=True)

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

@app.post('/api/llm')
def llm_process():
    data = request.get_json(force=True)
    text = data.get('text', '').strip()
    action = data.get('action', 'proofread')
    custom_prompt = data.get('custom_prompt', '').strip()
    
    if not text:
        return jsonify({'ok': False, 'error': '文字內容不可為空'}), 400
        
    prompts = {
        'proofread': "你是一位精通繁體中文的專業會議紀錄秘書。請根據輸入的「原始會議逐字稿內容」，在完全不改變原意的前提下，進行同音錯字修正、補上合適的標點符號、拿掉口吃贅字（例如：呃、然後、這個、那個、也就是說），並整理成通順、易讀的精美段落。請直接輸出整理後的逐字稿，不需說明或回答任何額外文字。",
        'diarization': "你是一位精通語境邏輯分析的 AI 秘書。請仔細閱讀下面「未區分發言人」的逐字稿內容。請根據對話的上下關係、稱呼、說話口氣、語意轉折與內容邏輯，將逐字稿進行「邏輯分段」，並加上講者標記（如：【講者 A】、【講者 B】等，如果有稱呼，可以直接替換為實際名字，如【張經理】、【小明】）。請直接輸出分段且標記講者後的逐字稿，不要輸出任何解釋或說明。",
        'minutes': "你是一位高效率的執行秘書。請將以下「會議逐字稿」內容進行整理，產出標準且精美的會議記錄。必須包含以下結構：\n1. 會議核心主題\n2. 重要決議事項 (關鍵點)\n3. 待辦追蹤清單 (Action Items，需指出負責人與任務項目，如果沒有提到負責人，請標記為全體或待定)\n請使用 markdown 格式美化輸出，讓整體結構清晰易讀，不要輸出任何前言或結尾解釋。",
        'summary': "你是一位專業的商業分析師。請精確地為以下「會議逐字稿」做一份摘要，提煉出最重要的核心關鍵與重點摘要，並以 Bullet points (條列式) 清晰呈現，直接給出最精準的精簡重點即可。",
    }
    
    system_prompt = prompts.get(action, prompts['proofread'])
    if action == 'custom' and custom_prompt:
        system_prompt = custom_prompt
        
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]
    
    payload = {
        "model": "gemma-4-e2b-it",
        "messages": messages,
        "temperature": 0.3,
        "stream": True
    }
    
    def generate():
        try:
            r = requests.post("http://127.0.0.1:18082/v1/chat/completions", json=payload, stream=True, timeout=600)
            if r.status_code != 200:
                yield f"data: {json.dumps({'error': 'Llama server returned error: ' + r.text}, ensure_ascii=False)}\n\n"
                return
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8').strip()
                    if decoded.startswith('data:'):
                        data_str = decoded[5:].strip()
                        if data_str == '[DONE]':
                            break
                        try:
                            obj = json.loads(data_str)
                            delta_obj = obj.get('choices', [{}])[0].get('delta', {})
                            
                            thought = delta_obj.get('reasoning_content', '')
                            delta = delta_obj.get('content', '')
                            
                            if thought:
                                yield f"data: {json.dumps({'thought': thought}, ensure_ascii=False)}\n\n"
                            if delta:
                                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
                        except Exception:
                            continue
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '8013')))
