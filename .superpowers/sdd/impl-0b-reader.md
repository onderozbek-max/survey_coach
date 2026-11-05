# Workstream 0B: reader / snapshot / server evidence

Branch `feature/surveycoach-mvp`. Synthetic data only, TDD (failing test first for every item), offline, in-memory DB, no push. Nine commits (`ffeb99a` … `e6e3d4f`, excluding 0A's `0a18882`). All new files are under 600 lines.

## Status per item

| # | Item | Result |
|---|---|---|
| 1 | Audit 2, duplicate labels | Fixed. Every choice control is kept with its own id. Grid columns merge by DOM column identity, rows by DOM row identity. |
| 2 | Audit 4, definition-only media | Fixed through provenance on the page plus a conservative review projection. 0A can refine per page (see handoff). |
| 3 | Audit 6, dedup reread | Fixed. One bundle per version, replaced or retained as a unit in one transaction. |
| 4 | Audit 11, error-only read | Fixed. Classified `reviewable` / `limited` / `error`; `error` never creates a review. |
| 5 | Audit 12, `pages_captured` | Fixed. Counts rendered captures. A capture manifest is exposed so the UI never guesses indices. |
| 6 | D1 stimulus | Done by reusing `timing._unrepresented_text`. Timing is identical (golden values 24.3 s / 20.7 s and a word-parity test). |
| 7 | D8 tri-state `required` | Done in snapshot, extract and definition, plus consumers I own. **`checks/structure.py` still needs 0A.** |
| 8 | D6 naming | Done. Historical stored titles are never rewritten. |
| 9 | Type detection | Done. Deterministic, with confidence, and a negative-control suite. |

## New or changed fields (UI and checks workers: this is your contract)

### Snapshot model (`surveycoach/snapshot.py`)

- `Question.required: bool | None = None` (was `bool = True`). `true` means the HTML `required` flag, or a definition field `required: true`. `false` means a visible RedJade "Optional" label, or a definition field `required: false`. `None` means the source did not say. Saved JSON with `true`/`false` is unchanged; a missing key loads as `None`. `site/phone.js` already shows "Optional" only for `=== false`, which is the correct behavior.
- The vendor "Optional" label is removed from `Question.text` when it sits on its own line or after sentence punctuation (it is UI, not wording). The raw observation JSON keeps it. A conflict (HTML required plus Optional label) gives `None`.
- `Page.visual_evidence: "rendered" | "definition_only" = "rendered"`. Definition-adapter pages start as `definition_only`. A page becomes `rendered` only through an explicit-ID merge with a rendered capture. Fully rendered reads are all `rendered`.
- `Page.declared_media: int = 0`. Count of `<img|video|iframe|picture>` tags in definition wording. It is only a presence signal: no loading or dimensions are invented, and `Page.media` stays empty.
- `Page.stimulus_text` is a read-only property (derived, not stored, not hashed). It is non-empty only for question pages. It is the page-scope prose left after timing's exact subtraction of question, help and answer text, with the trailing nav label and the vendor "Optional" label lines removed.
- `SurveySnapshot.all_pages_rendered -> bool` is true only when every page is `rendered`.
- `review_hash` omits `visual_evidence` when `"rendered"` and `declared_media` when `0`, so the hashes of versions saved before this work are unchanged. `definition_only` is different evidence and hashes differently. `content_hash` is unchanged.

### Coverage (`surveycoach/reader/models.py`)

- `visual_media_verified` is now actually set: `snapshot.all_pages_rendered`, set at the end of every read (definition or not).
- `read_outcome: "reviewable" | "limited" = "reviewable"`. Set by the server. Saved coverage without it loads as `reviewable`.
- `pages_captured` as stored equals the number of persisted capture rows (the server overwrites the reader's own claim). `pages_defined` remains the definition page count.

### Version detail payload (`GET /api/surveys/{id}[/versions/{v}]`)

- `snapshot.pages[i].stimulus_text: str`. Always recomputed, so stale injected values are overwritten. Media for question pages is `snapshot.pages[i].media`, which is already served.
- `captures: [{position:int, page_id:str}]`. The manifest of fetchable captures, contiguous from 0. Iterate this, not `coverage.pages_captured`, to build `/versions/{v}/captures/{position}` URLs.
- `survey_type_detection: {type, confidence (0..1), label ("low" <0.6 | "medium" | "high" >=0.8), reasons: [str]}`. It is a suggestion. `survey_type_chosen` keeps its meaning: it is true only after the user sets a type, never from auto-detection. Detection is also on every `GET /api/surveys` item.
- `title` is now: the user's own name (`display_title`), else the stored title unless generic, else the humanized slug, else the first stimulus heading, else the stored title. `title_confirmed: bool` is true when the user named it. `title_generic: bool` is true when the presented title is still generic, so the UI can ask for a name. `snapshot_title` and `versions[].title` stay the stored historical values.

### Reader job (`GET /api/jobs/{id}` for reader jobs)

- `pages_captured: int` counts rendered captures only (never definition pages). `GET /api/reader/jobs/{id}/preview/{n}` now resolves for every `n < pages_captured` (previews are always registered from the capture list), and is 404 otherwise.
- `outcome: "reviewable" | "limited" | "error" | null`. `error` means status `failed` with a safe fixed message that never echoes vendor text. `limited` means status `completed`: only legitimate welcome, closing or screen-out screens were read, so the UI should say "limited read". `reviewable` means questions were captured.
- `evidence: "new" | "replaced" | "retained" | null`. `retained` means a reread of the same version captured fewer screens than the stored bundle, so the stored coverage and captures were kept (the UI can say "kept your earlier, fuller read").

### Survey naming and type (`surveycoach/reader/naming.py`, `surveycoach/reader/survey_type.py`)

- `SLUG_PREFIXES = ("Insights", "HMS")` is the configured prefix list (owner to confirm). Only leading prefix words are stripped. Segments with digits, tokens, or random letters are rejected, and `?query`/`#fragment` are ignored. Generic titles: "Survey", "Surveys" (case and space insensitive).
- Read-time title priority: definition title, then slug, then first stimulus heading, then the document title. A generic document title survives only as a last resort so a read with real questions is not rejected.
- Detection (`services_concept`): a concept description (a stimulus of at least 40 words, or at least 20 words plus a concept cue such as imagine/idea/introducing) that precedes a purchase-interest question or buy-likelihood scale. Welcome and thank-you copy never count as descriptions. Confidence is 0.65 base, +0.10 for a concept cue, +0.15 for two or more cells, +0.05 for a likelihood scale (cap 0.95); no signal gives `non_ihut_product` at 0.4. `apply_detection` sets the type on a fresh read only when it still holds the default.

## Evidence rules worth knowing

- **Audit 4:** in `review.py`, if any page is not `rendered`, the image criteria `MEDIA_CRITERIA = ("7.2","7.3","7.5","7.6","B7")` are returned `assessed=False, fraction=None` (applies kept True). Findings from rendered pages are kept. This is applied after AI merging, so the judge cannot turn them back into assessed. Result: unchecked list plus `B7` in `pending_blockers`, so never N/A or passed. A rendered image-free survey is unchanged.
- **Audit 6:** `store_evidence` (`server/evidence.py`) replaces the bundle only if the new attempt captured at least as many screens. Otherwise it retains the prior bundle. Capture paths are validated before the version or job is created, so a bad manifest leaves nothing behind and no review job is stuck queued. `decisions` is never touched.
- **Audit 11:** `read_outcome` is `error` when the page copy (outside recognised welcome/closing/screen-out pages) matches an error pattern, or the reader stopped with `reader_error` and nothing recognisable was captured. Questions present always means `reviewable`.

## Handoff to worker 0A (I did not edit `checks/` or `signals.py`)

1. `checks/structure.py` lines ~206 and ~237 use `q.required` and `not q.required`. With the tri-state, `None` is treated as optional at ~237 (`any(q.kind in OPEN_TEXT and not q.required ...)`). Switch to `q.required is True` / `q.required is False`, so unknown is neither. Fixtures built without `required=` now get `None`.
2. Image checks can use `page.visual_evidence` and `page.declared_media` for per-page scoping. The review-level withholding above is a safe floor and is idempotent with any per-page logic you add.
3. `stimulus_text` is available on every `Page` for reading-level and claims checks on concept copy.
4. `tests/test_enrich_contract.py::test_scope_keeps_absent_ai_blockers_without_inventing_assessments` (4 params) fails with `checked_count` 20 vs the expected 21 and 32 vs 33. This comes from 0A's commit `0a18882`, not from 0B (I verified by reverting my `required` default and by disabling my review withholding). `tests/test_judge_schemas.py::test_the_batches_cover_everything_the_engine_says_is_waiting_on_ai` also fails ('Readable, light, and accessible' now unchecked); I verified it also fails with my `snapshot.py` reverted. Both are for 0A.

## Handoff to UI workers

- `Page.stimulus_text` renders above the question on question pages; `page.media` above it.
- Home and header: use `title_generic` to prompt for a name, and `survey_type_detection` (label plus reasons) for "Looks like a concept test, confirm". Do not treat `survey_type_chosen` as confirmed unless it is true.
- Share/About: build capture links from `captures[]`. `read_outcome === "limited"` and job `outcome`/`evidence` are the honest-read cues.

## Verification

- New suites: `test_reader_answer_identity`, `test_reader_observe_dom` (real Chromium, inline HTML), `test_required_tristate`, `test_visual_evidence`, `test_stimulus`, `test_survey_naming`, `test_reader_loopback_identity` (loopback server only), `test_server_naming`, `test_survey_type_detection`, `test_server_reader_evidence`. I mutation-checked the DOM tests (they fail if the JS facts are removed).
- Focused run: `tests/test_reader*.py test_timing*.py test_enrich*.py test_review*.py test_server*.py test_labels.py test_root_cause_invariants.py` plus the new suites and `test_checks_structure/judge_prompts/snapshot/canonical_reading_basis/mvp_reader_api/mvp_captures/phone_preview`: **586 passed, 5 failed** in the last full focused run. The five failures were the four 0A enrich-contract params above, and `test_labels.py::test_repository_projects_screens_for_each_round_without_writing_history`. That one was mine and is fixed (it now also pops the served `stimulus_text`, commit `e6e3d4f`; `test_labels.py` is 11 passed). I did not run the whole suite.
- Not touched: `site/`, `checks/`, `signals.py`. No push, no live calls, no real DB. Other workers' uncommitted changes in `site/` and `tests/test_phone_preview.py` are untouched, and `.superpowers/sdd/progress.md` stays staged and unchanged. The rename commit used a temporary index to avoid committing it.

## Known limits

- Stimulus text keeps whatever timing's whole-line subtraction leaves. Labels flattened onto one line (e.g. "YesNo") and progress text such as "3 / 16" can appear in the stimulus, exactly as timing already counts them. The heading detector ignores flattened answer labels. Cleaning those needs a change to timing's subtraction, which would break the parity guarantee, so I left it.
- The "Optional" DOM detection (a leaf element reading exactly "Optional" inside the question container) is verified against synthetic DOM only. Confirm against a real RedJade capture offline before relying on it. When it does not match, requiredness is `None`, which is the safe direction.
- A first reread after this change of a legacy survey can create a new version if the new title or survey type differs from the stored snapshot (both are review inputs). Existing versions and their stored titles are untouched.
- Detection recognises only the concept-then-intent pattern. Other types (`ihut`, `community_pulse`, `market_research`) are never auto-detected.
