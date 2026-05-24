#!/usr/bin/env python3
from flask import Flask, request, render_template, jsonify, send_file
from werkzeug.utils import secure_filename
import subprocess, time, uuid, pathlib, threading, os, signal

# Utilities for smart splitting
from audio_utils import get_audio_duration, find_silences, calculate_splits, split_audio, merge_subtitles, merge_texts

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

def process_job_thread(job_id, in_path, out_base, log_path, max_len, fmt):
    with lock:
        j = jobs.get(job_id)
        
    try:
        with open(log_path, 'a', encoding='utf-8') as logf:
            logf.write(f"Analyzing audio: {in_path}\n")
            logf.flush()
            
            duration = get_audio_duration(in_path)
            if duration > 0:
                logf.write(f"Duration: {duration:.2f}s\n")
                logf.write("Searching for silence points...\n")
                logf.flush()
                silences = find_silences(in_path)
                # Split every 10 mins (600s)
                splits = calculate_splits(duration, silences, 600)
                logf.write(f"Calculated {len(splits)} segments for processing.\n")
            else:
                logf.write("Failed to get duration, proceeding without split.\n")
                splits = [(0, 0)]
            logf.flush()
                
            segments = []
            if len(splits) > 1:
                logf.write("Splitting audio at silent points (this may take a moment)...\n")
                logf.flush()
                segments = split_audio(in_path, splits, UPLOAD_DIR, job_id)
            else:
                segments = [(in_path, 0.0)]
                
            all_txts = []
            all_srts = []
            all_vtts = []
            
            for idx, (seg_path, start_time) in enumerate(segments):
                seg_out_base = f"{out_base}_{idx}" if len(segments) > 1 else str(out_base)
                
                cmd = [str(WHISPER), '-m', str(MODEL), '-f', str(seg_path), '-of', seg_out_base, '-nt']
                cmd.extend(['-l', 'zh', '-ml', str(max_len), '-sow'])
                cmd.extend(['-et', '2.4', '-lpt', '-1.0'])
                cmd.append('-otxt')
                if fmt == 'srt' or fmt == 'vtt':
                    cmd.append('-osrt')
                    cmd.append('-ovtt')
                    
                logf.write(f"\n--- Transcribing Segment {idx+1}/{len(segments)} (Offset: {start_time:.2f}s) ---\n")
                logf.flush()
                
                proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, text=True)
                
                with lock:
                    if j['status'] == 'cancelled':
                        proc.kill()
                        return
                    j['proc'] = proc
                    j['pid'] = proc.pid
                
                rc = proc.wait()
                
                with lock:
                    if j['status'] == 'cancelled':
                        return
                        
                if rc != 0:
                    with lock:
                        j['status'] = 'failed'
                        j['returncode'] = rc
                    return
                    
                all_txts.append(f"{seg_out_base}.txt")
                if fmt == 'srt' or fmt == 'vtt':
                    all_srts.append((f"{seg_out_base}.srt", start_time))
                    all_vtts.append((f"{seg_out_base}.vtt", start_time))
                
            if len(segments) > 1:
                logf.write("\nMerging results...\n")
                logf.flush()
                merge_texts(all_txts, f"{out_base}.txt")
                if fmt == 'srt' or fmt == 'vtt':
                    merge_subtitles(all_srts, f"{out_base}.srt", is_srt=True)
                    merge_subtitles(all_vtts, f"{out_base}.vtt", is_srt=False)
                
                for seg_path, _ in segments:
                    pathlib.Path(seg_path).unlink(missing_ok=True)
                for txt in all_txts: pathlib.Path(txt).unlink(missing_ok=True)
                for srt, _ in all_srts: pathlib.Path(srt).unlink(missing_ok=True)
                for vtt, _ in all_vtts: pathlib.Path(vtt).unlink(missing_ok=True)
                
            logf.write("\nAll done.\n")
            logf.flush()
            
            with lock:
                if j['status'] == 'running':
                    j['status'] = 'done'
                    j['returncode'] = 0
                
    except Exception as e:
        with open(log_path, 'a', encoding='utf-8') as logf:
            logf.write(f"\nSystem Error: {str(e)}\n")
        with lock:
            if j['status'] == 'running':
                j['status'] = 'failed'
                j['returncode'] = -1


@app.route('/')
def index():
    return render_template('index.html')

@app.post('/api/upload_chunk')
def upload_chunk():
    upload_id = request.form.get('upload_id')
    chunk_index = request.form.get('chunk_index')
    chunk_data = request.files.get('file')
    
    print(f"[DEBUG] Received chunk {chunk_index} for upload {upload_id}")
    
    if not upload_id or chunk_index is None or chunk_data is None:
        print(f"[ERROR] Missing params: id={upload_id}, idx={chunk_index}, data={chunk_data is not None}")
        return jsonify({'ok': False, 'error': 'Missing parameters'}), 400
        
    temp_dir = UPLOAD_DIR / upload_id
    temp_dir.mkdir(exist_ok=True)
    
    chunk_path = temp_dir / chunk_index
    chunk_data.save(chunk_path)
    
    print(f"[DEBUG] Saved chunk {chunk_index} to {chunk_path}")
    return jsonify({'ok': True})

@app.post('/api/transcribe')
def transcribe():
    if not WHISPER.exists() or not MODEL.exists():
        return jsonify({'ok': False, 'error': '尚未安裝模型，先執行: bash scripts/install.sh'}), 400

    upload_id = request.form.get('upload_id')
    filename = request.form.get('filename')
    fmt = request.form.get('format', 'txt')
    max_len = request.form.get('max_len', '20')
    
    if upload_id:
        ext = pathlib.Path(filename).suffix.lower()
    else:
        f = request.files.get('file')
        if not f or not f.filename:
            return jsonify({'ok': False, 'error': '請先選擇音檔'}), 400
        filename = f.filename
        ext = pathlib.Path(filename).suffix.lower()

    if ext not in ALLOWED:
        return jsonify({'ok': False, 'error': f'不支援格式: {ext}'}), 400

    job_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    in_path = UPLOAD_DIR / f"{job_id}-{secure_filename(filename)}"
    out_base = RESULT_DIR / job_id
    log_path = LOG_DIR / f"{job_id}.log"
    
    if upload_id:
        temp_dir = UPLOAD_DIR / upload_id
        if not temp_dir.exists():
            return jsonify({'ok': False, 'error': 'Upload ID not found'}), 400
        chunks = sorted([int(p.name) for p in temp_dir.glob('*') if p.name.isdigit()])
        with open(in_path, 'wb') as outfile:
            for c in chunks:
                chunk_file = temp_dir / str(c)
                with open(chunk_file, 'rb') as infile:
                    outfile.write(infile.read())
                chunk_file.unlink()
        try:
            temp_dir.rmdir()
        except:
            pass
    else:
        f.save(in_path)

    # Initialize log file
    pathlib.Path(log_path).write_text(f"Job {job_id} started.\n", encoding='utf-8')

    with lock:
        jobs[job_id] = {
            'id': job_id, 'status': 'running', 'start_ts': time.time(), 'pid': None,
            'proc': None, 'input_path': str(in_path), 'output_base': str(out_base),
            'log_path': str(log_path), 'returncode': None, 'requested_format': fmt
        }
        
    t = threading.Thread(target=process_job_thread, args=(job_id, in_path, out_base, log_path, max_len, fmt))
    t.start()

    return jsonify({'ok': True, 'job_id': job_id, 'status': 'running'})

@app.get('/api/jobs/<job_id>')
def job_status(job_id):
    with lock:
        j = jobs.get(job_id)
    if not j:
        return jsonify({'ok': False, 'error': 'job not found'}), 404

    # Status is now managed entirely by the background thread.
    txt = ''
    main_output = j['output_base'] + '.' + j['requested_format']
    if j['status'] == 'done' and pathlib.Path(main_output).exists():
        txt = pathlib.Path(main_output).read_text(errors='ignore').strip()

    return jsonify({
        'ok': True, 'job_id': job_id, 'status': j['status'],
        'elapsed_sec': round(time.time() - j['start_ts'], 2),
        'returncode': j['returncode'], 'pid': j['pid'],
        'input_path': j['input_path'], 
        'text': txt, 'log_tail': tail_text(j['log_path'], 50),
    })

@app.get('/api/jobs/<job_id>/download')
def job_download(job_id):
    with lock:
        j = jobs.get(job_id)
    if not j or j['status'] != 'done':
        return "Not found or not ready", 404
    
    ext = request.args.get('ext', 'txt')
    target = pathlib.Path(j['output_base'] + '.' + ext)
    if not target.exists():
        return f"Format {ext} not available", 404
    
    return send_file(target, as_attachment=True)

@app.post('/api/jobs/<job_id>/cancel')
def job_cancel(job_id):
    with lock:
        j = jobs.get(job_id)
        if not j:
            return jsonify({'ok': False, 'error': 'job not found'}), 404
        if j['status'] != 'running':
            return jsonify({'ok': True, 'status': j['status']})
            
        j['status'] = 'cancelled'
        j['returncode'] = -15
        if j['proc']:
            try:
                os.kill(j['proc'].pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
                
    return jsonify({'ok': True, 'status': 'cancelled'})

if __name__ == '__main__':
    from waitress import serve
    port = int(os.environ.get('PORT', '8013'))
    print(f"Starting server with Waitress on 0.0.0.0:{port}")
    # Increase max_request_body_size to 10MB to accommodate 1MB chunks + multipart headers
    serve(app, host='0.0.0.0', port=port, threads=8, max_request_body_size=1073741824)