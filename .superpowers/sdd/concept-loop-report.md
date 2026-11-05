# Repeated-concept reader identity fix

Owner: `code-puppy-255b4e`

## Scope / root cause

The parent supplied actual-survey evidence of repeated concept trials with identical
question/option wording but different stimulus text. `OBSERVE.state_key` discarded
all surrounding wording whenever question groups existed. `extract.fingerprint()`
correctly hashes that key, so distinct concepts collided before extraction and
could be missed by progression or treated as loops.

## Changes

- `surveycoach/reader/observe.py`: append normalized visible contextual wording to
  question-page identity. Read actual DOM text nodes, not guessed concept labels.
- Exclude controls/answers, labels, output/contenteditable regions, declared
  feedback (`aria-describedby`, alerts/errors), live/status/timer/progress regions,
  script/style and hidden content. Retain existing question/option identity.
- Info-page identity is unchanged. Source page/question IDs still take precedence
  in extraction; synthetic IDs remain deterministic for the same observed concept.
- `extract.py` needed no production change: its existing state-key fingerprint
  contract now receives the missing contextual identity, covered directly in tests.
- No transport, permissions, participant mode, budget or safety-policy changes.

## TDD evidence

1. Added synthetic `tests/test_reader_concept_state.py` before implementation.
   Initial focused run: **3 failed, 3 passed**. The failures were the expected
   stimulus-only state/fingerprint collision and deterministic concept identity.
2. Implemented the minimal observation fix; the initial focused reader/regression
   selection passed **63 tests**.
3. Added parameterized synthetic end-to-end reader cases and verified against the
   pre-fix observer: **2 failed**. One silently skipped the second concept during
   bounded retries (2 captures instead of 3); the cyclic case stopped `blocked`
   instead of capturing both concepts and detecting their exact repeat.
4. Restored the fix: **8 concept-state tests passed**. Tests cover stimulus body and
   heading changes, checked/value changes, feedback/countdown/status/answer effects,
   hidden content, exact repeats/restoration, source IDs, direct fingerprint use,
   two-trial progression and true-loop detection.

Final focused verification:

```sh
.venv/bin/python -m pytest \
  tests/test_reader_concept_state.py tests/test_reader_browser.py \
  tests/test_reader_adaptive.py tests/test_reader_participate.py \
  tests/test_reader_recovery.py tests/test_reader_media_state.py \
  tests/test_reader_strategy_safety.py -q
# 71 passed in 88.69s
```

`git diff --check` passed. Bare `python` lacked pytest; all meaningful test runs
used the existing project `.venv` without dependency installation.

## Boundaries / remaining validation

- Browser fixtures are entirely synthetic (`about:blank` with requests aborted,
  plus loopback-only reader server); no external/live survey was accessed.
- No delegation, full-suite run or push.
- Parent owns actual authorized test-survey validation and participant preview.
- Context filtering relies on declared feedback/live/timer semantics (and existing
  error conventions); arbitrary unmarked dynamic prose cannot be distinguished
  perfectly from real stimulus wording. No broad fuzzy text filtering introduced.
- Only owned implementation, new focused tests and this report are committed;
  pre-existing staged `.superpowers/sdd/progress.md` and review assets are excluded.
