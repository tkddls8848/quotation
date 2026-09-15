"""Local/API host for isolated HWP conversions. Run one process behind TLS for deployment."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import atexit
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import uuid

import olefile
from pypdf import PdfReader

MAX_INPUT = 32 * 1024 * 1024
MAX_OUTPUT = 64 * 1024 * 1024
TTL = 15 * 60
IMAGE = os.environ.get('HWP_IMAGE', 'quotation-hwp-converter:local')
ROOT = Path(os.environ.get('HWP_JOB_ROOT', str(Path(__file__).resolve().parents[2] / '.cache/hwp-jobs'))).resolve()
ORIGINS = set(os.environ.get('HWP_ALLOWED_ORIGINS', 'http://127.0.0.1:18574,http://localhost:5173,http://127.0.0.1:5173').split(','))
SERVICE_KEY = os.environ.get('HWP_SERVICE_KEY', '')


def validate_hwp(data):
    try:
        with olefile.OleFileIO(BytesIO(data)) as doc:
            header = doc.openstream('FileHeader').read(256)
            if not header.startswith(b'HWP Document File') or len(header) < 40 or header[35] != 5:
                raise ValueError('HWP 5.0 형식이 아닙니다.')
            flags = int.from_bytes(header[36:40], 'little')
            if flags & (2 | 4):
                raise ValueError('암호화·배포용 HWP는 보안을 해제한 사본을 사용하세요.')
            if not doc.exists('BodyText/Section0'):
                raise ValueError('본문이 없는 HWP입니다.')
    except (OSError, IOError) as error:
        raise ValueError('올바른 HWP 5.0 파일이 아닙니다.') from error


def docker(*args, timeout=15):
    return subprocess.run(['docker', *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout, check=False)


def remove_job(path):
    # Only this service's explicitly marked UUID job directories can be removed.
    if path.parent != ROOT or not re.fullmatch(r'job-[0-9a-f]{32}', path.name) or not (path / '.owned').is_file():
        raise ValueError('Not an owned job directory')
    shutil.rmtree(path)


@dataclass
class Job:
    id: str
    token: str
    path: Path
    expires: float
    state: str = 'queued'
    message: str = ''
    cancel: threading.Event = field(default_factory=threading.Event)


class Manager:
    def __init__(self):
        ROOT.mkdir(parents=True, exist_ok=True)
        self.jobs = {}
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.slots = threading.BoundedSemaphore(4)
        self.stop = threading.Event()
        # Stale marked work is never offered after a restart.
        for path in ROOT.iterdir():
            if re.fullmatch(r'job-[0-9a-f]{32}', path.name) and (path / '.owned').is_file():
                docker('rm', '-f', 'hwp-' + path.name[4:])
                remove_job(path)
        threading.Thread(target=self.cleanup_loop, daemon=True).start()

    def create(self, data):
        validate_hwp(data)
        with self.lock:
            if len(self.jobs) >= 16 or not self.slots.acquire(blocking=False):
                raise OverflowError('서버가 처리 중입니다. 잠시 후 다시 시도하세요.')
            job_id = uuid.uuid4().hex
            path = ROOT / ('job-' + job_id)
            try:
                path.mkdir(mode=0o700)
                (path / '.owned').touch()
                (path / 'input').mkdir()
                (path / 'output').mkdir(mode=0o777)
                (path / 'output').chmod(0o777)
                (path / 'input/source.hwp').write_bytes(data)
                job = Job(job_id, secrets.token_urlsafe(32), path, time.time() + TTL)
                self.jobs[job.id] = job
                self.pool.submit(self.convert, job)
                return job
            except Exception:
                self.slots.release()
                if (path / '.owned').exists(): remove_job(path)
                raise

    def convert(self, job):
        name = 'hwp-' + job.id
        try:
            with self.lock:
                if job.cancel.is_set(): return
                job.state = 'running'
            command = [
                'create', '--name', name, '--network', 'none', '--read-only',
                '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=1g',
                '--memory-swap=1g', '--cpus=1', '--pids-limit=128',
                '--ulimit', f'fsize={MAX_OUTPUT}:{MAX_OUTPUT}',
                '--tmpfs', '/tmp:rw,nosuid,size=256m,mode=1777',
                '--mount', f'type=bind,source={job.path / "input"},target=/input,readonly',
                '--mount', f'type=bind,source={job.path / "output"},target=/output', IMAGE,
            ]
            created = docker(*command, timeout=30)
            if created.returncode: raise ValueError('변환 컨테이너를 시작하지 못했습니다.')
            if job.cancel.is_set(): return
            result = docker('start', '-a', name, timeout=120)
            if job.cancel.is_set(): return
            pdf = job.path / 'output/source.pdf'
            if result.returncode or not pdf.is_file() or not 0 < pdf.stat().st_size <= MAX_OUTPUT:
                raise ValueError('변환에 실패했습니다. 파일 손상이나 지원하지 않는 문서 요소를 확인하세요.')
            with pdf.open('rb') as stream:
                reader = PdfReader(stream)
                if reader.is_encrypted or not len(reader.pages): raise ValueError('유효한 PDF가 생성되지 않았습니다.')
            with self.lock:
                if not job.cancel.is_set(): job.state = 'done'
        except subprocess.TimeoutExpired:
            job.state, job.message = 'failed', '변환 제한 시간(120초)을 초과했습니다.'
        except Exception as error:
            job.state = 'failed'
            job.message = str(error) if isinstance(error, ValueError) else '변환 서버에서 작업을 처리하지 못했습니다.'
        finally:
            try: docker('rm', '-f', name)
            except (OSError, subprocess.TimeoutExpired): pass
            with self.lock:
                if job.cancel.is_set(): job.state, _ = 'cancelled', self.jobs.pop(job.id, None)
                # Source is no longer needed. Other artifacts survive only until TTL.
                (job.path / 'input/source.hwp').unlink(missing_ok=True)
                if job.state != 'done' and (job.path / '.owned').exists(): remove_job(job.path)
            self.slots.release()

    def find(self, job_id, token):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or not hmac.compare_digest(job.token, token): raise KeyError()
            if time.time() >= job.expires: raise TimeoutError()
            return job

    def cancel_job(self, job):
        job.cancel.set()
        # If cancellation races container creation, worker's post-run check still prevents download.
        docker('rm', '-f', 'hwp-' + job.id)
        with self.lock:
            if job.state in ('done', 'failed', 'cancelled') and (job.path / '.owned').exists(): remove_job(job.path)
            # A finished job that the owner deleted must not keep holding a slot.
            # While one is still running its own worker releases it on the way out.
            if job.state != 'running': job.state, _ = 'cancelled', self.jobs.pop(job.id, None)

    def cleanup_loop(self):
        while not self.stop.wait(15):
            with self.lock:
                expired = [job for job in self.jobs.values() if time.time() >= job.expires]
            for job in expired:
                self.cancel_job(job)
                with self.lock:
                    if job.state != 'running': self.jobs.pop(job.id, None)

    def close(self):
        self.stop.set()
        for job in list(self.jobs.values()): self.cancel_job(job)
        self.pool.shutdown(wait=True)


class Handler(BaseHTTPRequestHandler):
    server_version = 'DocumentConverter'
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, *_): pass  # Do not log tokens, filenames or document content.

    def origin_ok(self):
        origin = self.headers.get('Origin')
        return not origin or origin in ORIGINS

    def reply(self, code, payload, mime='application/json'):
        data = json.dumps(payload, ensure_ascii=False).encode() if mime == 'application/json' else payload
        self.send_response(code)
        origin = self.headers.get('Origin')
        if origin in ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        if mime == 'application/pdf': self.send_header('Content-Disposition', 'attachment; filename="converted.pdf"')
        self.end_headers()
        try: self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError): pass

    def do_OPTIONS(self):
        if not self.origin_ok(): self.reply(403, {'error': '허용되지 않은 출처입니다.'}); return
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin', ''))
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Service-Key')
        self.end_headers()

    def handle_request(self):
        manager = self.server.manager
        if not self.origin_ok(): self.reply(403, {'error': '허용되지 않은 출처입니다.'}); return
        if self.command == 'GET' and self.path == '/health':
            try: ready = docker('image', 'inspect', IMAGE).returncode == 0
            except (OSError, subprocess.TimeoutExpired): ready = False
            self.reply(200, {'ready': ready, 'requiresKey': bool(SERVICE_KEY), 'maxBytes': MAX_INPUT, 'retentionSeconds': TTL}); return
        if SERVICE_KEY and not hmac.compare_digest(self.headers.get('X-Service-Key', ''), SERVICE_KEY):
            self.reply(401, {'error': '서버 접근키를 확인하세요.'}); return
        if self.command == 'POST' and self.path == '/jobs':
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if self.headers.get('Transfer-Encoding') or not 0 < size <= MAX_INPUT:
                    self.reply(413, {'error': 'HWP 입력은 32MB까지 지원합니다.'}); return
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/octet-stream':
                    self.reply(415, {'error': '바이너리 HWP 파일을 보내세요.'}); return
                data = self.rfile.read(size)
                if len(data) != size: raise ValueError('업로드가 완료되지 않았습니다.')
                job = manager.create(data)
                self.reply(202, {'id': job.id, 'token': job.token, 'expiresAt': job.expires}); return
            except ValueError as error: self.reply(400, {'error': str(error)}); return
            except OverflowError as error: self.reply(429, {'error': str(error)}); return
        match = re.fullmatch(r'/jobs/([0-9a-f]{32})(/result)?', self.path)
        if match:
            try: job = manager.find(match[1], self.headers.get('Authorization', '').removeprefix('Bearer '))
            except KeyError: self.reply(404, {'error': '작업을 찾을 수 없습니다.'}); return
            except TimeoutError: self.reply(410, {'error': '작업이 만료되었습니다. 다시 변환하세요.'}); return
            if self.command == 'DELETE' and not match[2]:
                manager.cancel_job(job); self.reply(200, {'state': 'cancelled'}); return
            if self.command == 'GET':
                with manager.lock:
                    if match[2]:
                        if job.state != 'done': self.reply(409, {'error': '아직 다운로드할 수 없습니다.'}); return
                        self.reply(200, (job.path / 'output/source.pdf').read_bytes(), 'application/pdf'); return
                    self.reply(200, {'state': job.state, 'message': job.message, 'expiresAt': job.expires}); return
        self.reply(404, {'error': '경로를 찾을 수 없습니다.'})

    def dispatch(self):
        try: self.handle_request()
        except Exception: self.reply(500, {'error': '서버 오류가 발생했습니다. 잠시 후 다시 시도하세요.'})
    do_GET = dispatch
    do_POST = dispatch
    do_DELETE = dispatch


if __name__ == '__main__':
    host = os.environ.get('HWP_BIND', '127.0.0.1')
    if host not in ('127.0.0.1', 'localhost', '::1') and not SERVICE_KEY:
        raise SystemExit('HWP_SERVICE_KEY is required for non-loopback binding')
    server = ThreadingHTTPServer((host, int(os.environ.get('HWP_PORT', '8788'))), Handler)
    server.manager = Manager()
    atexit.register(server.manager.close)
    print(f'HWP conversion API: http://{host}:{server.server_port}', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
