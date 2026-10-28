"""Small, bounded YouTube audio service for the Chordroom frontend."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse
import uuid

ALLOWED_ORIGINS = set(os.environ.get('ALLOWED_ORIGINS', 'https://wonderer1004-maker.github.io,http://127.0.0.1:4173,http://localhost:4173').split(','))
ROOT = Path(tempfile.mkdtemp(prefix='chordroom-'))
JOBS = {}
RATES = {}
LOCK = threading.Lock()
SLOT = threading.BoundedSemaphore(1)
TTL = 600

def canonical_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('올바른 YouTube 영상 링크를 입력해주세요.')
    u = urlparse(value)
    if u.scheme != 'https' or u.username or u.password or u.port not in (None, 443):
        raise ValueError('https YouTube 영상 링크만 지원합니다.')
    host = (u.hostname or '').lower()
    parts = u.path.strip('/').split('/')
    if host == 'youtu.be':
        video = parts[0]
    elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'www.youtube-nocookie.com'):
        video = parse_qs(u.query).get('v', [''])[0] if u.path == '/watch' else (parts[1] if len(parts) == 2 and parts[0] in ('shorts', 'embed', 'live') else '')
    else:
        raise ValueError('YouTube 링크만 지원합니다.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
        raise ValueError('영상 ID를 확인해주세요. 재생목록만 있는 링크는 지원하지 않습니다.')
    return 'https://www.youtube.com/watch?v=' + video

def clean_jobs():
    now = time.time()
    with LOCK:
        expired = [key for key, job in JOBS.items() if now-job['created'] > TTL and job['status'] not in ('pending', 'processing')]
        for key in expired:
            JOBS.pop(key, None)
            shutil.rmtree(ROOT / key, ignore_errors=True)
        for ip in list(RATES):
            RATES[ip] = [t for t in RATES[ip] if now-t < TTL]
            if not RATES[ip]:
                del RATES[ip]

def public_job(key):
    with LOCK:
        job = JOBS.get(key)
        if not job:
            return None
        return {k: v for k, v in job.items() if k not in ('path', 'created')}

def update(key, **values):
    with LOCK:
        JOBS[key].update(values)

def run_extraction(key, url):
    folder = ROOT / key
    try:
        folder.mkdir()
        update(key, status='processing', message='영상 정보를 확인하고 있습니다.')
        common = [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-playlist', '--no-warnings', '--socket-timeout', '15', '--retries', '1', '--js-runtimes', 'node']
        meta = subprocess.run(common + ['--dump-single-json', '--skip-download', url], capture_output=True, text=True, timeout=60)
        if meta.returncode:
            raise RuntimeError(extractor_error(meta.stderr))
        info = json.loads(meta.stdout)
        duration = info.get('duration') or 0
        if info.get('is_live') or duration <= 0 or duration > 600:
            raise RuntimeError('길이가 확인되는 10분 이하 일반 영상만 지원합니다. 라이브·긴 영상은 제외됩니다.')
        if info.get('age_limit', 0) >= 18:
            raise RuntimeError('로그인이나 연령 확인이 필요한 영상은 지원하지 않습니다.')
        update(key, message='음원을 내려받고 MP3로 변환하고 있습니다.')
        command = common + ['--max-filesize', '40M', '--format', 'bestaudio/best', '--extract-audio', '--audio-format', 'mp3', '--audio-quality', '128K', '--no-progress', '--output', str(folder/'audio.%(ext)s'), url]
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        target = folder/'audio.mp3'
        if result.returncode or not target.is_file():
            raise RuntimeError(extractor_error(result.stderr))
        if target.stat().st_size > 50*1024*1024:
            raise RuntimeError('변환 결과가 다운로드 제한 크기를 초과했습니다.')
        title = (info.get('track') or info.get('title') or 'YouTube audio')[:160]
        update(key, status='ready', message='MP3 추출이 완료됐습니다. 10분 안에 내려받아주세요.', created=time.time(), title=title, artist=(info.get('artist') or info.get('creator') or info.get('uploader') or '')[:160], duration=duration, size=target.stat().st_size, path=str(target), download=f'/api/extractions/{key}/file')
    except subprocess.TimeoutExpired:
        update(key, status='failed', message='처리 시간이 초과됐습니다. 잠시 후 다른 영상으로 시도해주세요.')
    except Exception as error:
        update(key, status='failed', message=str(error) if isinstance(error, RuntimeError) else '음원을 처리하지 못했습니다. 영상 링크와 공개 상태를 확인해주세요.')
    finally:
        SLOT.release()
        if public_job(key)['status'] == 'failed':
            shutil.rmtree(folder, ignore_errors=True)

def extractor_error(detail):
    lower = detail.lower()
    if any(word in lower for word in ('sign in', 'bot', 'cookies', '403', 'po token')):
        return 'YouTube가 이 서버의 다운로드를 제한했습니다. 로그인·봇 차단·접근 제한을 우회하지 않으며 이 영상은 추출할 수 없습니다.'
    if any(word in lower for word in ('private', 'unavailable', 'members', 'copyright', 'removed')):
        return '비공개·삭제·회원 전용 등 접근할 수 없는 영상입니다.'
    return 'YouTube 음원 추출에 실패했습니다. 다른 공개 영상으로 시도해주세요.'

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Avoid logging video URLs or download capability IDs.

    def cors(self):
        origin = self.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')

    def json(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        clean_jobs()
        path = urlparse(self.path).path
        if path in ('/', '/health'):
            return self.json(200, {'status': 'ok', 'service': 'chordroom-audio', 'maxDuration': 600})
        match = re.fullmatch(r'/api/extractions/([a-f0-9]{32})(/file)?', path)
        if not match:
            return self.json(404, {'message': '요청한 항목이 없습니다.'})
        key, file_request = match.groups()
        job = public_job(key)
        if not job:
            return self.json(404, {'message': '작업이 만료됐거나 서버가 재시작됐습니다. 다시 추출해주세요.'})
        if not file_request:
            return self.json(200, job)
        with LOCK:
            target = JOBS[key].get('path')
        if job['status'] != 'ready' or not target or not Path(target).is_file():
            return self.json(409, {'message': '아직 다운로드할 수 없습니다.'})
        try:
            with open(target, 'rb') as file:
                self.send_response(200)
                self.cors()
                self.send_header('Content-Type', 'audio/mpeg')
                self.send_header('Content-Length', str(Path(target).stat().st_size))
                self.send_header('Content-Disposition', "attachment; filename=audio.mp3; filename*=UTF-8''"+quote(job['title']+'.mp3', safe=''))
                self.end_headers()
                shutil.copyfileobj(file, self.wfile)
        except (BrokenPipeError, ConnectionResetError, FileNotFoundError):
            pass

    def do_POST(self):
        if urlparse(self.path).path != '/api/extractions':
            return self.json(404, {'message': '요청한 항목이 없습니다.'})
        if self.headers.get('Origin') not in ALLOWED_ORIGINS:
            return self.json(403, {'message': '허용된 코드룸 웹앱에서 요청해주세요.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('요청 크기를 확인해주세요.')
            body = json.loads(self.rfile.read(length))
            url = canonical_url(body.get('url'))
        except (ValueError, TypeError, AttributeError):
            return self.json(400, {'message': '올바른 https YouTube 영상 링크를 입력해주세요.'})
        clean_jobs()
        # Render supplies this forwarding header; untrusted direct deployments
        # fall back to the socket address and should sit behind a rate limiter.
        ip = self.headers.get('X-Forwarded-For', self.client_address[0]).split(',')[0].strip()
        with LOCK:
            if len(RATES.get(ip, [])) >= 5 or len(JOBS) >= 20:
                return self.json(429, {'message': '요청이 많습니다. 10분 후 다시 시도해주세요.'})
            if not SLOT.acquire(blocking=False):
                return self.json(429, {'message': '다른 음원을 처리하고 있습니다. 완료 후 다시 시도해주세요.'})
            key = uuid.uuid4().hex
            JOBS[key] = {'id': key, 'status': 'pending', 'message': '추출을 준비하고 있습니다.', 'created': time.time()}
            RATES.setdefault(ip, []).append(time.time())
        threading.Thread(target=run_extraction, args=(key, url), daemon=True).start()
        return self.json(202, public_job(key))

def reaper():
    while True:
        time.sleep(30)
        clean_jobs()

if __name__ == '__main__':
    threading.Thread(target=reaper, daemon=True).start()
    port = int(os.environ.get('PORT', '8787'))
    print(f'Chordroom audio listening on {port}', flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
