"""Offline board evidence. Own server + empty disposable DB; never read a user's DB.

Run from the project: .venv/bin/python scripts/capture_screens.py
Use --serve for an isolated, seeded manual QA session; Ctrl-C cleans it up.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]
# Direct script invocation puts scripts/, not the repository, on sys.path.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
AFTER = ROOT / 'review' / 'after'
VIEWPORTS = {'desktop': {'width': 1440, 'height': 900},
             'mobile': {'width': 390, 'height': 844}}


SNACKS = ('Fruit \U0001F34E', 'Crackers', 'Nuts')


def pattern_snapshot():
    """Actual repeated engine input, not a synthetic override of review output. Three questions share one
    answer label with an emoji, so the engine raises the same "Emoji in an answer choice" check with the
    same paste on each and the plan groups them (different rewrites never merge)."""
    return {'title': 'Synthetic grouped instructions', 'source_url': 'fixture://board-pattern',
            'pages': [
                {'id': 'intro', 'position': 0, 'kind': 'intro',
                 'intro_text': 'Welcome! Help us choose snacks. This takes about 2 minutes.'},
                *[{'id': f'p{i}', 'position': i, 'kind': 'question', 'questions': [
                    {'id': f'q{i}', 'kind': 'multi_choice', 'text': text,
                     'options': [{'id': f'o{n}', 'label': label} for n, label in enumerate(SNACKS)]}]}
                  for i, text in enumerate(('Which snacks do you buy?',
                                            'Which snacks do you share?',
                                            'Which snacks do you pack?'), 1)],
                {'id': 'thanks', 'position': 4, 'kind': 'thank_you',
                 'intro_text': 'Thank you for helping us choose snacks.'}]}


def poll(read, ready, *, timeout, process=None, label='operation'):
    deadline = time.monotonic() + timeout
    while True:
        if process is not None and process.poll() is not None:
            raise RuntimeError(f'Server exited during {label}; inspect server.log')
        value = read()
        if ready(value):
            return value
        if time.monotonic() >= deadline:
            raise TimeoutError(f'Timed out waiting for {label}')
        time.sleep(.1)


def request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def wait_job(client, job_id, timeout):
    def completed(job):
        if job['status'] == 'failed':
            raise RuntimeError(f"Synthetic job failed: {job.get('error')}")
        return job['status'] == 'completed'
    return poll(lambda: request(client, 'GET', f'/api/jobs/{job_id}'), completed,
                timeout=timeout, label='synthetic review job')


def seed(client, timeout):
    if request(client, 'GET', '/api/surveys')['surveys']:
        raise RuntimeError('Capture requires an empty temporary database')
    sample = request(client, 'POST', '/api/samples/boxer-briefs', json={})
    wait_job(client, sample['job_id'], timeout)
    detail = request(client, 'GET', f"/api/surveys/{sample['id']}")
    group = next((item for name in ('must_fix', 'quick_wins', 'more')
                  for item in detail['plan'][name] if len(item['fingerprints']) > 1), None)
    pattern_detail = detail
    if group is None:
        created = request(client, 'POST', '/api/surveys',
                          json={'snapshot': pattern_snapshot(), 'ai': False})
        wait_job(client, created['job_id'], timeout)
        pattern_detail = request(client, 'GET', f"/api/surveys/{created['id']}")
        group = next((item for name in ('must_fix', 'quick_wins', 'more')
                      for item in pattern_detail['plan'][name]
                      if len(item['fingerprints']) > 1), None)
    if not group or not detail['plan']['must_fix']:
        raise RuntimeError('Expected a real grouped item and a sample must-fix')
    return detail, pattern_detail, group


def worker_environment(*, managed_reader=False):
    """Captures stay isolated; manual QA may retain one validated reader setting."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('SURVEYCOACH_', 'WIBEY_', 'OPENAI_', 'ANTHROPIC_'))}
    if managed_reader and os.environ.get('SURVEYCOACH_CORPORATE_PROXY'):
        from surveycoach.reader.proxy import corporate_proxy
        corporate_proxy('app.redjade.net')  # Fail closed before starting a child.
        env['SURVEYCOACH_CORPORATE_PROXY'] = os.environ['SURVEYCOACH_CORPORATE_PROXY']
    return env


@contextmanager
def server(log_path, timeout, *, managed_reader=False):
    """Pass an already bound socket: no free-port discovery/rebind race."""
    with tempfile.TemporaryDirectory(prefix='surveycoach-board-') as temporary:
        with socket.socket() as listener, log_path.open('w') as log:
            listener.bind(('127.0.0.1', 0))
            listener.listen(128)
            port = listener.getsockname()[1]
            env = worker_environment(managed_reader=managed_reader)
            env.update(SC_CAPTURE_DB=str(Path(temporary) / 'empty.db'),
                       SC_CAPTURE_FD=str(listener.fileno()),
                       PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get('PYTHONPATH', ''))
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker'],
                                       cwd=ROOT, env=env, pass_fds=(listener.fileno(),),
                                       stdout=log, stderr=subprocess.STDOUT)
            try:
                base = f'http://127.0.0.1:{port}'
                with httpx.Client(base_url=base, trust_env=False, timeout=2) as client:
                    def health():
                        try:
                            return client.get('/api/metadata').status_code == 200
                        except httpx.TransportError:
                            return False
                    poll(health, bool, timeout=timeout, process=process, label='startup')
                    yield base, client
            finally:
                # Only the process we spawned; never search for or kill by port/name.
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                else:
                    process.wait()


def output_path(value):
    path = Path(value).resolve()
    if not path.is_relative_to(AFTER.resolve()):
        raise argparse.ArgumentTypeError('Output must be review/after/ or a child directory')
    return path


def capture(browser, base, detail, pattern, group, output, reduced_motion, client):
    records = []
    diagnostics = []
    for device, viewport in VIEWPORTS.items():
        latest = request(client, 'GET', f"/api/surveys/{detail['id']}")
        for fingerprint in latest['decisions']:
            request(client, 'PUT', f"/api/surveys/{detail['id']}/versions/{detail['version']}/decisions/{fingerprint}",
                    json={'action': 'open'})
        context = browser.new_context(viewport=viewport, device_scale_factor=1,
                                      reduced_motion='reduce' if reduced_motion else 'no-preference',
                                      permissions=['clipboard-read', 'clipboard-write'],
                                      service_workers='block')
        blocked, errors = [], []
        def local_only(route):
            if urlsplit(route.request.url).netloc == urlsplit(base).netloc:
                route.continue_()
            else:
                blocked.append(route.request.url)
                route.abort()
        context.route('**/*', local_only)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))

        def review(data, chapter):
            page.goto(f"{base}/review.html?id={data['id']}#{chapter}")
            page.wait_for_function('SC.reviewReady === true')
            page.locator(f'#chapter-{chapter}').wait_for(state='visible')

        def snap(name, scenario):
            page.evaluate('document.fonts.ready')
            page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
            page.evaluate('scrollTo(0, 0)')
            metrics = page.evaluate('''() => ({width: innerWidth, height: innerHeight,
                scrollWidth: document.documentElement.scrollWidth,
                primaryButtons: [...document.querySelectorAll('.btn-primary')].filter(e =>
                    e.checkVisibility() && !e.closest('[inert]')).length,
                aboutReachable: !!document.querySelector('#about-review')?.checkVisibility()})''')
            path = output / f'{device}-{name}.png'
            page.screenshot(path=str(path), full_page=True)
            records.append({'file': path.name, 'scenario': scenario, 'viewport': viewport,
                            'metrics': metrics, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'visually_inspected': False})
            if metrics['scrollWidth'] > metrics['width']:
                raise RuntimeError(f'Horizontal overflow in {device}-{name}')

        try:
            page.goto(base + '/local.html')
            page.locator('#sample-start').wait_for()
            snap('home', 'empty-temp-db seeded with synthetic sample')
            review(detail, 'overview')
            snap('overview', 'pinned offline sample')
            page.locator('#start-improving').click()
            page.locator('#coach .card').wait_for()
            first = detail['plan']['must_fix'][0]['fingerprints'][0]
            page.wait_for_function("fp => !!document.querySelector('#coach [data-fingerprint=\"' + fp + '\"]')", arg=first)
            snap('improve', 'first sample must-fix')
            review(pattern, 'improve')
            page.evaluate("fp => dispatchEvent(new CustomEvent('surveycoach-focus-finding', {detail:fp}))",
                          group['fingerprints'][0])
            page.wait_for_function('n => document.querySelectorAll(".pattern-row").length === n',
                                   arg=len(group['fingerprints']))
            snap('improve-pattern', 'engine-generated group; ' + pattern['snapshot']['source_url'])
            review(detail, 'improve')
            # Choose actual engine wording through the UI, scoped to this disposable DB.
            page.locator('#use-change').click()
            page.locator('#undo').wait_for()
            share_link = page.locator('#chapter-nav [data-chapter=share]')
            if not share_link.is_visible():      # narrow headers collapse the steps into a menu
                page.locator('#steps-button').click()
            share_link.click()
            page.locator('#change-list li').first.wait_for()
            snap('share', 'one synthetic decision chosen in UI; no launch verification')
            review(detail, 'overview')
            page.locator('#preview-member').click()
            dialog = page.get_by_role('dialog', name='Preview as a member')
            dialog.wait_for()
            dialog.get_by_role('button', name='Pause', exact=True).click()
            snap('preview-member', 'paused local reconstructed walkthrough, not RedJade')
            diagnostics.append({'device': device, 'page_errors': errors,
                                'blocked_external_requests': blocked})
            if errors or blocked:
                raise RuntimeError(f'Browser errors={errors}; blocked external requests={blocked}')
        finally:
            context.close()
    return records, diagnostics


def worker():
    # No default server entrypoint: it could select a real DB or live provider.
    import uvicorn
    from surveycoach.server import create_app
    db = Path(os.environ['SC_CAPTURE_DB'])
    if db.exists():
        raise RuntimeError('Worker refuses an existing database')
    app = create_app(db, provider=None)
    uvicorn.run(app, fd=int(os.environ['SC_CAPTURE_FD']), log_level='warning')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=output_path, default=AFTER,
                        help='Output directory inside review/after (default: review/after)')
    parser.add_argument('--timeout', type=float, default=60, help='Startup/job deadline in seconds')
    parser.add_argument('--reduced-motion', action='store_true', help='Emulate prefers-reduced-motion')
    parser.add_argument('--serve', action='store_true', help='Serve disposable seeded DB for manual QA until Ctrl-C')
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be finite and positive')
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {'status': 'running', 'visual_inspection': 'NOT inspected', 'records': []}
    manifest_path = args.output / 'evidence.json'
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        with server(args.output / 'server.log', args.timeout, managed_reader=args.serve) as (base, client):
            detail, pattern, group = seed(client, args.timeout)
            manifest.update(sample_id=detail['id'], pattern_id=pattern['id'],
                            group_fingerprints=group['fingerprints'], reduced_motion=args.reduced_motion,
                            provenance='Empty temporary DB; pinned offline boxer-briefs; engine-generated synthetic group; no overrides')
            urls = {name: f"{base}/review.html?id={data['id']}#{chapter}"
                    for name, data, chapter in [('overview', detail, 'overview'),
                                                ('improve', detail, 'improve'),
                                                ('pattern', pattern, 'improve'), ('share', detail, 'share')]}
            print(json.dumps({'home': base + '/local.html', **urls}, indent=2), flush=True)
            if args.serve:
                print('Disposable QA server. Ctrl-C to stop and delete DB.', flush=True)
                while True:
                    time.sleep(1)
            from playwright.sync_api import sync_playwright
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    manifest['records'], manifest['browser_checks'] = capture(
                        browser, base, detail, pattern, group, args.output, args.reduced_motion, client)
                finally:
                    browser.close()
            manifest['status'] = 'completed'
        manifest['server_cleanup'] = 'owned process waited; temporary database removed'
    except KeyboardInterrupt:
        manifest.update(status='stopped', server_cleanup='owned process waited; temporary database removed')
    except Exception as error:
        manifest.update(status='failed', error=str(error))
        raise
    finally:
        signal.signal(signal.SIGTERM, previous)
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    for record in manifest['records']:
        print(args.output / record['file'])
    print(manifest_path)


if __name__ == '__main__':
    if sys.argv[1:] == ['--worker']:
        worker()
    else:
        main()
