import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('audio_service', Path(__file__).with_name('app.py'))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class AudioServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app.ROOT = Path(self.tmp.name)
        app.JOBS.clear()
        app.RATES.clear()
        app.SLOT = threading.BoundedSemaphore(1)

    def tearDown(self):
        self.tmp.cleanup()

    def test_url_whitelist(self):
        expected = 'https://www.youtube.com/watch?v=BaW_jenozKc'
        for value in ['https://youtu.be/BaW_jenozKc?t=5', 'https://music.youtube.com/watch?v=BaW_jenozKc&list=any', 'https://www.youtube.com/shorts/BaW_jenozKc', 'https://www.youtube.com/embed/BaW_jenozKc']:
            self.assertEqual(app.canonical_url(value), expected)
        for value in ['http://youtube.com/watch?v=BaW_jenozKc', 'https://youtube.com.evil.test/watch?v=BaW_jenozKc', 'https://youtube.com@127.0.0.1/watch?v=BaW_jenozKc', 'https://youtube.com:7777/watch?v=BaW_jenozKc', 'https://youtube.com/playlist?list=x', 'https://127.0.0.1/a', None, 'https://youtu.be/../etc/passwd']:
            with self.assertRaises(ValueError, msg=str(value)):
                app.canonical_url(value)

    def pending(self, key='a'*32):
        self.assertTrue(app.SLOT.acquire(False))
        app.JOBS[key] = {'id': key, 'status': 'pending', 'created': time.time()}
        return key

    def test_download_ready_and_private_path(self):
        key = self.pending()
        def fake_run(args, **_):
            if '--dump-single-json' in args:
                return subprocess.CompletedProcess(args, 0, json.dumps({'duration': 12.5, 'title': '테스트 곡', 'artist': 'Test artist'}), '')
            target = Path(args[args.index('--output')+1].replace('%(ext)s', 'mp3'))
            target.write_bytes(b'ID3-test-audio')
            return subprocess.CompletedProcess(args, 0, '', '')
        with patch.object(app.subprocess, 'run', fake_run):
            app.run_extraction(key, 'https://www.youtube.com/watch?v=BaW_jenozKc')
        job = app.public_job(key)
        self.assertEqual(job['status'], 'ready')
        self.assertEqual(job['artist'], 'Test artist')
        self.assertNotIn('path', job)
        self.assertNotIn('created', job)
        self.assertTrue(app.SLOT.acquire(False))

    def test_long_video_blocked_before_download(self):
        key = self.pending()
        with patch.object(app.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{"duration": 601}', '')) as runner:
            app.run_extraction(key, 'https://www.youtube.com/watch?v=BaW_jenozKc')
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(app.public_job(key)['status'], 'failed')
        self.assertTrue(app.SLOT.acquire(False))

    def test_timeout_and_bot_error(self):
        key = self.pending()
        with patch.object(app.subprocess, 'run', side_effect=subprocess.TimeoutExpired([], 1)):
            app.run_extraction(key, 'https://www.youtube.com/watch?v=BaW_jenozKc')
        self.assertEqual(app.public_job(key)['status'], 'failed')
        self.assertIn('제한', app.extractor_error('Sign in to confirm you are not a bot'))

    def test_expired_files_deleted(self):
        key = 'b'*32
        folder = app.ROOT/key
        folder.mkdir()
        (folder/'audio.mp3').write_bytes(b'test')
        app.JOBS[key] = {'created': time.time()-app.TTL-1, 'status': 'ready'}
        app.clean_jobs()
        self.assertIsNone(app.public_job(key))
        self.assertFalse(folder.exists())

    def handler(self, path, body=None, origin='https://wonderer1004-maker.github.io'):
        h = app.Handler.__new__(app.Handler)
        h.path = path
        raw = json.dumps(body).encode() if body is not None else b''
        h.headers = {'Origin': origin, 'Content-Length': str(len(raw))}
        h.client_address = ('127.0.0.1', 1)
        h.rfile, h.wfile = io.BytesIO(raw), io.BytesIO()
        h.response_headers = {}
        h.send_response = lambda code: setattr(h, 'code', code)
        h.send_header = lambda key, value: h.response_headers.update({key: value})
        h.end_headers = lambda: None
        return h

    def test_http_validation_busy_and_download(self):
        h = self.handler('/api/extractions', {'url': 'https://example.com/music'})
        h.do_POST()
        self.assertEqual(h.code, 400)
        h = self.handler('/api/extractions', {'url': 'https://youtu.be/BaW_jenozKc'}, origin='https://evil.test')
        h.do_POST()
        self.assertEqual(h.code, 403)
        with patch.object(app.threading, 'Thread'):
            h = self.handler('/api/extractions', {'url': 'https://youtu.be/BaW_jenozKc'})
            h.do_POST()
        self.assertEqual(h.code, 202)
        job = json.loads(h.wfile.getvalue())
        busy = self.handler('/api/extractions', {'url': 'https://youtu.be/BaW_jenozKc'})
        busy.do_POST()
        self.assertEqual(busy.code, 429)
        status = self.handler('/api/extractions/'+job['id'])
        status.do_GET()
        self.assertEqual(json.loads(status.wfile.getvalue())['status'], 'pending')
        key = job['id']
        folder = app.ROOT/key
        folder.mkdir()
        target = folder/'audio.mp3'
        target.write_bytes(b'ID3-test-audio')
        app.update(key, status='ready', path=str(target), title='테스트 음악')
        download = self.handler('/api/extractions/'+key+'/file')
        download.do_GET()
        self.assertEqual(download.code, 200)
        self.assertEqual(download.wfile.getvalue(), b'ID3-test-audio')
        self.assertEqual(download.response_headers['Content-Type'], 'audio/mpeg')
        self.assertIn('filename*=UTF-8', download.response_headers['Content-Disposition'])
        self.assertEqual(download.response_headers['Access-Control-Allow-Origin'], 'https://wonderer1004-maker.github.io')

if __name__ == '__main__':
    unittest.main()
