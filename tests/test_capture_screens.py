"""Capture runner safety and real offline lifecycle; synthetic temporary DB only."""
import hashlib
import json
import socket
import subprocess
import sys

import httpx
from PIL import Image
import pytest

from scripts import capture_screens as capture


def test_output_cannot_escape_after():
    for path in (capture.ROOT / 'review', capture.ROOT / 'uglyhome.png',
                 capture.AFTER / '..' / 'originals'):
        with pytest.raises(capture.argparse.ArgumentTypeError):
            capture.output_path(path)
    assert capture.output_path(capture.AFTER / 'reduced') == capture.AFTER / 'reduced'


def test_poll_handles_delayed_success_deadline_and_dead_process(monkeypatch):
    monkeypatch.setattr(capture.time, 'sleep', lambda _: None)
    values = iter([False, False, True])
    assert capture.poll(lambda: next(values), bool, timeout=1)
    with pytest.raises(TimeoutError, match='synthetic'):
        capture.poll(lambda: False, bool, timeout=0, label='synthetic')
    class Dead:
        def poll(self):
            return 1
    with pytest.raises(RuntimeError, match='Server exited'):
        capture.poll(lambda: True, bool, timeout=1, process=Dead())


def test_failed_job_fails_promptly():
    def respond(request):
        return httpx.Response(200, json={'status': 'failed', 'error': 'offline test failure'})
    with httpx.Client(transport=httpx.MockTransport(respond), base_url='http://localhost') as client:
        with pytest.raises(RuntimeError, match='offline test failure'):
            capture.wait_job(client, 'synthetic', 1)


def test_seed_refuses_nonempty_db():
    calls = []
    def respond(request):
        calls.append(request.method)
        return httpx.Response(200, json={'surveys': [{'id': 'unexpected'}]})
    with httpx.Client(transport=httpx.MockTransport(respond), base_url='http://localhost') as client:
        with pytest.raises(RuntimeError, match='empty temporary'):
            capture.seed(client, 1)
    assert calls == ['GET']


def test_real_server_cleanup_on_exception_and_actual_group(tmp_path):
    with pytest.raises(RuntimeError, match='forced capture failure'):
        with capture.server(tmp_path / 'server.log', 20) as (base, client):
            detail, pattern, group = capture.seed(client, 20)
            assert detail['example'] is True
            assert pattern['snapshot']['source_url'] == 'fixture://board-pattern'
            assert pattern['review']['ai'] is None
            assert len(group['fingerprints']) == 3
            members = [f for f in pattern['review']['findings']
                       if f['fingerprint'] in group['fingerprints']]
            assert len({f['question_id'] for f in members}) == 3
            assert {f['criterion_id'] for f in members} == {'3.3'}
            port = httpx.URL(base).port
            raise RuntimeError('forced capture failure')
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', port)) != 0


def test_manual_qa_server_sigterm_cleanup():
    import tempfile
    capture.AFTER.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=capture.AFTER, prefix='test-serve-') as output:
        process = subprocess.Popen([sys.executable, str(capture.ROOT / 'scripts/capture_screens.py'),
                                    '--serve', '--output', output], cwd=capture.ROOT,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            # Poll a file-independent live process until seed + URL printing is complete.
            import select
            ready, _, _ = select.select([process.stdout], [], [], 20)
            assert ready, 'Manual QA server did not print URLs'
            process.terminate()
            stdout, stderr = process.communicate(timeout=20)
            assert process.returncode == 0, stdout + stderr
            evidence = json.loads((capture.Path(output) / 'evidence.json').read_text())
            assert evidence['status'] == 'stopped'
            assert evidence['server_cleanup'] == 'owned process waited; temporary database removed'
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


def test_real_capture_all_views_and_preserves_originals(tmp_path):
    originals = [*capture.ROOT.glob('review/*.png'), capture.ROOT / 'uglyhome.png']
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in originals if path.exists()}
    import tempfile
    capture.AFTER.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=capture.AFTER, prefix='test-') as output:
        result = subprocess.run([sys.executable, str(capture.ROOT / 'scripts/capture_screens.py'),
                                 '--output', output, '--reduced-motion'],
                                cwd=capture.ROOT, capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
        manifest = json.loads((capture.Path(output) / 'evidence.json').read_text())
        assert manifest['status'] == 'completed'
        assert manifest['visual_inspection'] == 'NOT inspected'
        assert manifest['reduced_motion'] is True
        assert all(not check['page_errors'] and not check['blocked_external_requests']
                   for check in manifest['browser_checks'])
        assert manifest['server_cleanup'] == 'owned process waited; temporary database removed'
        assert len(manifest['records']) == 12
        assert len({r['file'] for r in manifest['records']}) == 12
        for record in manifest['records']:
            path = capture.Path(output) / record['file']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
            with Image.open(path) as image:
                assert image.width == record['viewport']['width']
                assert image.height >= record['viewport']['height']
            assert record['metrics']['scrollWidth'] <= record['viewport']['width']
            assert record['visually_inspected'] is False
            assert str(path) in result.stdout
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before}
