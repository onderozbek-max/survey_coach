# Bounded participant revisits

Owner: `code-puppy-7e5678`

## Root cause

After the stimulus identity fix (`09da003`), the parent found an actual-test
follow-up screen with legitimately identical wording and options after distinct
concept screens. Session-wide `previous` membership stopped on its second visit.
A rendered fingerprint is not a unique capture-instance identifier.

## Implementation

- `session.py`: participant mode counts directed transitions between rendered
  fingerprints. Two traversals of an identical transition are allowed; the third
  stops with `loop` before capture/answering that destination. Consecutive identical
  fingerprints stop immediately. Passive mode retains its original global-set
  loop behavior.
- A generic screen after distinct concepts has different incoming transitions,
  so legitimate revisits are captured. Synthetic occurrence IDs never enter loop
  detection. A two-state cycle captures five pages, then stops on its third A→B
  transition. Truly stuck pages still return `blocked` through bounded progression.
- `extract.py`: optional existing pages provide collision-aware page/question ID
  allocation. First occurrences preserve source IDs (or their existing hashes).
  Collisions get deterministic `stable_id(prefix, original, 'occurrence', n)` IDs;
  candidates are checked against all occupied IDs, including source IDs that might
  match an occurrence ID. Option IDs are generated from allocated question IDs.
- Capture metadata and callbacks use allocated IDs consistently. Original source
  IDs remain untouched in raw observation JSON. No new source/definition identity
  claims or fuzzy merging were added.

## Bounds / unchanged behavior

Maximum 30 pages and the existing transport deadline/async timeout remain intact.
No transport, approval, write/submission permissions, repair budgets, observation
logic or adaptive strategies were modified. This heuristic intentionally stops
ambiguous paths after repeated identical transitions rather than claiming all
revisits are safe. Consecutive visually identical pages remain unprovable progress.

## TDD and focused verification

New separate test file: `tests/test_reader_revisits.py`.

Before production edits: **5 failed, 1 passed**. Both concept/follow-up paths
stopped `loop`; page-limit case also stopped early; the cycle count exposed the
old first-revisit cutoff; the extraction test showed the missing allocation API.

After implementation and additional invariants: **83 passed in 102.80s**:

```sh
.venv/bin/python -m pytest tests/test_reader_revisits.py \
  tests/test_reader_concept_state.py tests/test_reader_browser.py \
  tests/test_reader_participate.py tests/test_reader_passive.py \
  tests/test_reader_adaptive.py tests/test_reader_recovery.py -q
```

Coverage includes A→follow-up→B→same-follow-up→C→end (six captures/five questions),
with and without source IDs, unique page/question/option/capture IDs, deterministic
reruns/content hashes, bounded genuine cycles, stuck page, consecutive exact-state
protection, caller page budget, source question reuse across different pages,
and collision candidates already occupied by a source ID. Existing passive
exact-repeat loop tests remain unchanged and passing.

`git diff --check` passed. All browser requests were synthetic loopback traffic.
No live/external requests, delegation, full-suite run, push or real participant
retries. Parent owns authorized actual-test validation and server import checks.
Pre-existing staged progress and review assets are excluded from the named-file
commit; only session.py, extract.py, the new tests and this report are owned here.
