"""Escaped, director-readable sign-off packet; technical detail is opt-in."""
from difflib import SequenceMatcher
from html import escape
from math import floor
import re

from surveycoach.server.review_card import review_card
from surveycoach.server.rounds import change_sheet, presentation, valid_decisions
from surveycoach.signals import SIGNALS
from surveycoach.status import NOT_CHECKED_LABEL, is_decided
from surveycoach.quality import build_quality
from surveycoach.rubric import load_rubric


def quality_section(detail):
    """Score and coverage for experts only: closed by default, never the headline."""
    q = (detail.get("methodology") or {}).get("quality") or build_quality(detail.get("review") or {}, load_rubric())
    value = f"{floor(q['score'] + .5)}/100" if q['score'] is not None else "Not assessed"
    status = "Provisional" if q["provisional"] else "Assessed"
    return (f"<details><summary>Quality methodology</summary>"
            f"<h2>Survey Quality · {value}</h2>"
            f"<p>{status} · {floor(q['coverage_percent'] + .5)}% coverage of applicable rubric weight · "
            f"{q['blockers']['flagged']} must-fix risks · {q['blockers']['unchecked']} risk checks unverified.</p>"
            "<p>Earned assessed applicable points / assessed applicable points × 100. "
            "Criterion weights come from the rubric. N/A weight is excluded; missing checks are unknown. "
            "Coverage is assessed weight / applicable weight, separate from quality. "
            "The old raw score used all 100 rubric points; it is not this normalized score. "
            "Display values are rounded, not extra precision. A high score is not readiness or launch approval. "
            "AI checks may be missing or fallible; unverified risk checks keep the score provisional. "
            "Choices and acknowledged risks cannot improve assessed quality before rechecking. "
            "Member outcomes were not measured.</p></details>")


def verdict_lines(detail):
    """Headline, one-sentence story and tile counts, escaped, from the one verdict."""
    verdict = (detail.get("overview") or {}).get("verdict") if detail.get("review") else None
    if not verdict:
        return [f"<h2>{_text('Review not available')}</h2>"]
    tiles = verdict["tiles"]
    lines = [f"<h2>{_text(verdict['headline'])}</h2>"]
    if verdict["story"]:
        lines.append(f"<p>{_text(verdict['story'])}</p>")
    lines.append(f"<p>Fix {tiles['fix']} · Improve {tiles['improve']} · You check {tiles['you_check']} · "
                 f"{_text(verdict['time']['label'])}.</p>")
    return lines


def summary_packet(detail, *, download=False):
    if download:
        return stakeholder_packet(detail)

    def text(value):
        return escape(str(value if value is not None else ""), quote=True)

    summary = detail.get("presentation") or presentation(detail)
    parts = ["<!doctype html><html lang='en'><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width,initial-scale=1'>",
             "<title>SurveyCoach stakeholder summary</title><style>",
             "body{font:16px/1.5 system-ui;color:#18332e;max-width:850px;margin:2rem auto;padding:1rem}"
             "h1,h2,h3{line-height:1.2}section{break-inside:avoid}li{margin:.5rem 0}"
             "details{border-top:1px solid #bbb;margin-top:2rem;padding-top:1rem}"
             "@media print{body{font-size:11pt;margin:0}details{break-before:page}}",
             "</style><body><main><p>SurveyCoach · Share with stakeholders · not launch approval</p>",
             f"<h1>{text(detail['title'])}</h1><p>Version {detail['version']}</p>",
             *verdict_lines(detail), *review_card(detail),
             f"<p><strong>What we checked:</strong> {text(summary['scope']['summary'])}</p>"]
    parts.extend(f"<p>{text(line)}</p>" for line in summary["scope"]["unchecked_paths"])
    parts.append(quality_section(detail))
    parts.append("<p>Keep as is acknowledges a risk; it is not evidence that an issue was corrected. "
                 "SurveyCoach does not edit RedJade. Manual completion is not verified.</p>")
    lines = detail.get("change_sheet") or change_sheet(detail)
    for action, title in (("pick", "Chosen changes"), ("keep", "Kept risks")):
        selected = [line for line in lines if line["action"] == action]
        parts.append(f"<section><h2>{title}</h2><ul>")
        if not selected:
            parts.append("<li>None recorded.</li>")
        for line in selected:
            parts.append(f"<li><strong>{text(line['screen_label'])} · {text(line['target'])}</strong>")
            if action == "pick":
                if line.get('edit_kind') == 'add_answer':
                    parts.append(f"<p>Keep question: {text(line['find'])}<br>Add answer option: {text(line['replace'])}</p>"
                                 f"<p>{text(line.get('instructions',''))}</p>")
                else:
                    parts.append(f"<p>Find: {text(line['find'])}<br>Replace: {text(line['replace'])}</p>")
                if line.get("manual_edit_required"):
                    parts.append("<p>Review the source manually; this change is not a verified text replacement.</p>")
            else:
                parts.append(f"<p>{text(line['find'])}<br>Reason: {text(line['reason'])} (acknowledged risk)</p>")
            parts.append("</li>")
        parts.append("</ul></section>")
    changes = detail.get("round_changes", {})
    parts.append("<section><h2>What changed since the previous version</h2>")
    if not changes.get("compared_to_round"):
        parts.append("<p>First version: no previous comparison.</p>")
    else:
        parts.append(f"<p>Compared with Version {text(changes['compared_to_round'])}: "
                     f"{len(changes.get('fixed', []))} no longer flagged, "
                     f"{len(changes.get('still', []))} still flagged, "
                     f"{len(changes.get('new', []))} newly flagged, "
                     f"{len(changes.get('uncertain', []))} not verified.</p><ul>")
        for key in ("fixed", "still", "new", "uncertain"):
            for item in changes.get(key, []):
                parts.append(f"<li><strong>{text(item['screen_label'])}: {text(item['resolution'])}</strong>"
                             f"<p>Before: {text(item['old_wording'])}<br>Now: {text(item['new_wording'])}</p></li>")
        parts.append("</ul>")
    parts.append("</section><details><summary>Technical appendix: evidence and limits</summary>")
    coverage = detail.get("coverage") or {}
    parts.extend(f"<p>{text(warning)}</p>" for warning in coverage.get("warnings", []))
    review = detail.get("review")
    if review:
        card = review["scorecard"]
        earned = round(card["score"] if "checked_points" in card else card["score"] - card["unchecked_points"], 2)
        checked = card.get("checked_points", 100 - card["unchecked_points"])
        parts.append(f"<p>{earned:g} of {checked} checked points earned; "
                     f"{card['unchecked_points']} points unchecked. Not automatic launch approval.</p>")
        parts.append("<h3>Not checked</h3><ul>")
        parts.extend(f"<li>{text(title)}</li>" for title in review.get("unchecked", []))
        parts.append("</ul>")
        if review.get("ai") is None:
            parts.append("<p>AI wording review was not requested.</p>")
        elif review["ai"].get("failed"):
            parts.append("<p>Some AI checks could not finish; their results remain unknown.</p>")
        if card.get("pending_blockers"):
            parts.append("<p>Some launch-risk checks remain unverified.</p>")
        parts.append("<h3>Observed issues</h3><ul>")
        for finding in review.get("findings", []):
            parts.append(f"<li><strong>{text(finding['headline'])}</strong>"
                         f"<p>{text(finding['evidence'])}</p><p>{text(finding['explanation'])}</p></li>")
        parts.append("</ul>")
    else:
        parts.append("<p>Review not available. No readiness judgement has been made.</p>")
    return "\n".join([*parts, "</details></main></body></html>"])


# Copied from Part B Task 1: downloadable files deliberately have no asset dependencies.
_LIGHT_CSS = """
:root{--bg:#F7F8FA;--surface:#FFFFFF;--surface-2:#F1F4F8;--line:#E3E8EF;
--text:#0F1B2D;--muted:#5B6B80;--accent:#0067A0;--accent-soft:#E6F1F8;
--critical:#B42318;--critical-soft:#FEF3F2;--positive:#067647;--positive-soft:#ECFDF3}
body{background:var(--bg);color:var(--text);font:16px/1.5 -apple-system,
BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;max-width:850px;margin:2rem auto;padding:1rem}
h1,h2,h3{line-height:1.2;letter-spacing:-.02em}h1{font-size:40px}h2{font-size:28px}
section{background:var(--surface);border:1px solid var(--line);border-radius:20px;
padding:24px;margin:24px 0;overflow-wrap:anywhere}p,li{white-space:pre-wrap}
li{margin:.75rem 0}.meta{color:var(--muted)}table{border-collapse:collapse;width:100%}
th,td{text-align:left;border-bottom:1px solid var(--line);padding:12px;vertical-align:top}
th{color:var(--accent);background:var(--accent-soft)}
del{color:var(--critical);background:var(--critical-soft)}
ins{color:var(--positive);background:var(--positive-soft)}
@media(max-width:600px){body{margin:0}section{padding:16px}th,td{padding:6px}}
@media print{body{background:var(--surface);font-size:11pt;margin:0}li,tr{break-inside:avoid}}
"""


def _text(value):
    return escape(str(value if value is not None else ""), quote=True)


def attachment_filename(title, version):
    """ASCII allowlist, bounded title, no paths, quotes or header controls."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-")[:80].rstrip("-")
    return f"surveycoach-{slug or 'survey'}-v{int(version)}.html"


def _word_diff(before, after):
    old, new = re.findall(r"\s+|[^\s]+", before or ""), re.findall(r"\s+|[^\s]+", after or "")
    pieces = []
    for operation, start, end, new_start, new_end in SequenceMatcher(
            None, old, new, autojunk=False).get_opcodes():
        if operation == "equal":
            pieces.append(_text("".join(old[start:end])))
        else:
            if operation in {"delete", "replace"}:
                pieces.append(f"<del>{_text(''.join(old[start:end]))}</del>")
            if operation in {"insert", "replace"}:
                pieces.append(f"<ins>{_text(''.join(new[new_start:new_end]))}</ins>")
    return "".join(pieces)


def stakeholder_packet(detail):
    """Read-only stakeholder story; choices are intent, never proof of source edits."""
    decisions = valid_decisions(detail)
    projected = dict(detail, decisions=decisions)
    scope = presentation(projected)["scope"]
    review = detail.get("review") or {}
    overview = detail.get("overview") or {}
    parts = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width,initial-scale=1'>",
             "<title>SurveyCoach stakeholder summary</title>",
             f"<style>{_LIGHT_CSS}</style></head><body><main>",
             "<p class='meta'>SurveyCoach · Share with stakeholders · not launch approval</p>",
             f"<h1>{_text(detail['title'])}</h1><p>Version {_text(detail['version'])}</p>",
             "<section>", *verdict_lines(detail), "</section>", *review_card(detail),
             "<section><h2>Member experience</h2><table>",
             "<thead><tr><th>Signal</th><th>State</th><th>What we know</th></tr></thead><tbody>"]
    signals = overview.get("signals") if review else None
    for signal in signals or [{"name": name, "label": NOT_CHECKED_LABEL, "summary": NOT_CHECKED_LABEL}
                              for _, name, _ in SIGNALS]:
        parts.append(f"<tr><td>{_text(signal['name'])}</td><td>{_text(signal['label'])}</td>"
                     f"<td>{_text(signal['summary'])}</td></tr>")
    parts.append("</tbody></table></section><section><h2>Changes chosen</h2>"
                 "<p>Chosen changes are not verified source edits. SurveyCoach does not edit RedJade. "
                 "Manual completion is not verified.</p><ul>")
    lines = change_sheet(projected)
    chosen = [line for line in lines if line["action"] == "pick"]
    if not chosen:
        parts.append("<li>None recorded.</li>")
    for line in chosen:
        parts.append(f"<li><strong>{_text(line['screen_label'])} · {_text(line['target'])}</strong>")
        if line.get("edit_kind") == "add_answer":
            parts.append(f"<p>Keep question: {_text(line['find'])}</p>"
                         f"<p>Add answer option: <ins>{_text(line['replace'])}</ins></p>"
                         f"<p>{_text(line.get('instructions', ''))}</p>")
        else:
            parts.append(f"<p>{_word_diff(line['find'], line['replace'])}</p>")
        if line.get("manual_edit_required"):
            parts.append("<p>Review the source manually; this change is not a verified text replacement.</p>")
        parts.append("</li>")
    parts.append("</ul></section><section><h2>Kept on purpose</h2><ul>")
    kept = [line for line in lines if line["action"] == "keep" and line["reason"].strip()]
    if not kept:
        parts.append("<li>None recorded.</li>")
    for line in kept:
        parts.append(f"<li><strong>{_text(line['screen_label'])} · {_text(line['target'])}</strong>"
                     f"<p>{_text(line['find'])}</p><p>Reason: {_text(line['reason'])}</p>"
                     "<p>Acknowledged risk, not evidence that an issue was corrected.</p></li>")
    parts.append("</ul></section><section><h2>Still open</h2>")
    open_findings = []
    for finding in review.get("findings", []):
        if finding.get("absorbed_by"):
            continue
        if not is_decided(decisions.get(finding["fingerprint"])):
            open_findings.append(finding)
    parts.append(f"<p>{len(open_findings)} findings still need a choice.</p><ul>" if review
                 else "<p>Review not available; open findings are not yet known.</p><ul>")
    parts.extend(f"<li>{_text(finding['headline'])}<p>{_text(finding.get('explanation', ''))}</p></li>"
                 for finding in open_findings)
    parts.append("</ul></section><section><h2>What we checked / not checked</h2>")
    parts.append(f"<p>{_text(scope['summary'])}</p>")
    parts.extend(f"<p>{_text(line)}</p>" for line in scope["unchecked_paths"])
    parts.extend(f"<p>{_text(line)}</p>" for line in (detail.get("coverage") or {}).get("warnings", []))
    if review:
        card = review.get("scorecard", {})
        parts.append(quality_section(detail))
        parts.append("<details><summary>Not checked automatically</summary>")
        if card:
            earned = card["score"] if "checked_points" in card else card["score"] - card["unchecked_points"]
            checked = card.get("checked_points", 100 - card["unchecked_points"])
            parts.append(f"<p>{_text(earned)} of {_text(checked)} checked points earned; "
                         f"{_text(card['unchecked_points'])} points unchecked.</p>")
        listed = (detail.get("methodology") or {}).get("not_checked_automatically")
        titles = [entry["title"] for entry in listed] if listed is not None else review.get("unchecked", [])
        parts.append("<ul>" + "".join(f"<li>{_text(item)}</li>" for item in titles) + "</ul></details>")
        if review.get("ai") is None:
            parts.append("<p>AI wording review was not requested.</p>")
        elif review["ai"].get("failed"):
            parts.append("<p>Some AI checks could not finish; their results remain unknown.</p>")
        if card.get("pending_blockers"):
            parts.append("<p>Some launch-risk checks remain unverified.</p>")
    else:
        parts.append("<p>Review not available. No readiness judgement has been made.</p>")
    parts.append("<p>Member outcomes and preferences were not measured. Timing is an estimate, "
                 "not an observation of members.</p></section></main></body></html>")
    return "\n".join(parts)
