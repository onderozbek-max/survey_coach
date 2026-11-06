#!/usr/bin/env python3
"""Build the GitHub Pages bundle from site/.

Usage: python scripts/build_pages.py [output-folder]   (default: _site)

The bundle's front door (index.html) is the landing page; the sample review moves to sample.html. The server-only
pages (local.html, review.html) call /api, which a static host does not have, so they become redirects back to the
front door instead of dead ends. Only site/ is ever copied.
"""
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ONLY_PAGES = ('local.html', 'review.html')
LANDING = 'welcome.html'
SAMPLE_LINK_IN_SOURCE = 'href="index.html" data-sample-link'     # in the source tree the sample is index.html
SAMPLE_LINK_IN_BUNDLE = 'href="sample.html"'
REDIRECT = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta http-equiv="refresh" content="0; url=index.html"><title>SurveyCoach sample</title></head>'
            '<body><p>This public page shows a sample review only. '
            '<a href="index.html">Go to the SurveyCoach sample</a>.</p></body></html>\n')
KEEP_OUT = shutil.ignore_patterns('*.py', '*.md', '*.log', '*.bak', '*.db', '*.sqlite', '.DS_Store', '__pycache__')


def build(site: pathlib.Path, out: pathlib.Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(site, out, ignore=KEEP_OUT, dirs_exist_ok=True)
    (out / 'index.html').replace(out / 'sample.html')
    landing = (out / LANDING).read_text().replace(SAMPLE_LINK_IN_SOURCE, SAMPLE_LINK_IN_BUNDLE)
    (out / 'index.html').write_text(landing)
    (out / LANDING).unlink()
    for name in SERVER_ONLY_PAGES:
        (out / name).write_text(REDIRECT)
    (out / '.nojekyll').write_text('')


if __name__ == '__main__':
    target = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / '_site'
    build(ROOT / 'site', target)
    print(f'wrote {target}')
