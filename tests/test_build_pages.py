"""The GitHub Pages bundle: the static sample, and nothing that would dead-end on a static host.

The server-only pages (local.html, review.html) call /api, which does not exist on Pages, so the bundle swaps
them for redirects back to the sample. Only the site/ folder is ever copied: no docs, reports or fixtures.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_pages  # noqa: E402


def build(tmp_path):
    out = tmp_path / '_site'
    build_pages.build(ROOT / 'site', out)
    return out


def test_bundle_has_the_sample_and_its_assets(tmp_path):
    out = build(tmp_path)
    for name in ('index.html', 'data.js', 'environment.js', 'app.js', 'design-system.css', 'sample-banner.js'):
        assert (out / name).is_file(), name
    assert '.nojekyll' in {p.name for p in out.iterdir()}


def test_server_only_pages_redirect_to_the_sample(tmp_path):
    out = build(tmp_path)
    for name in ('local.html', 'review.html'):
        page = (out / name).read_text()
        assert 'http-equiv="refresh"' in page and 'url=index.html' in page
        assert 'href="index.html"' in page            # a plain link too, for browsers that ignore refresh
        assert '/api/' not in page and '<script' not in page


def test_nothing_outside_site_is_copied(tmp_path):
    out = build(tmp_path)
    names = {p.name for p in out.rglob('*')}
    assert not names & {'.superpowers', 'docs', 'fixtures', 'spikes', 'tests', 'surveycoach', 'review', '.git'}
    assert not [p for p in out.rglob('*') if p.suffix in {'.py', '.md', '.log', '.bak', '.db', '.sqlite'}]


def test_the_private_server_environment_is_not_baked_in(tmp_path):
    out = build(tmp_path)
    env = (out / 'environment.js').read_text()
    assert 'SURVEYCOACH_LOCAL = false' in env and 'SURVEYCOACH_LOCAL = true' not in env
    assert 'SURVEYCOACH_DEVELOPER' not in env


def test_the_bundle_contains_no_urls_except_the_team_address_slot(tmp_path):
    out = build(tmp_path)
    data = (out / 'data.js').read_text()
    assert 'http://' not in data and 'https://' not in data


def test_command_line_builds_into_the_given_folder(tmp_path):
    target = tmp_path / 'bundle'
    result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_pages.py'), str(target)],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert (target / 'index.html').is_file()


def test_the_workflow_publishes_the_built_bundle_not_the_raw_site_folder():
    workflow = (ROOT / '.github' / 'workflows' / 'pages.yml').read_text()
    assert 'python3 scripts/build_pages.py _site' in workflow
    assert 'path: _site' in workflow and 'path: site\n' not in workflow
    assert 'needs: test' not in workflow                  # publishing the static sample does not wait on the suite
    assert workflow.count('pytest -q') == 1               # ...but the suite still runs, so a red run stays visible
