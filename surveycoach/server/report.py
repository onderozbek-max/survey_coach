"""Escaped, director-readable sign-off packet; technical detail is opt-in."""
from html import escape

from surveycoach.server.rounds import change_sheet, presentation


def summary_packet(detail):
    def text(value):
        return escape(str(value if value is not None else ""), quote=True)

    summary = detail.get("presentation") or presentation(detail)
    minutes = max(1, round(detail.get("total_seconds", 0) / 60))
    parts = ["<!doctype html><html lang='en'><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width,initial-scale=1'>",
             "<title>SurveyCoach sign-off summary</title><style>",
             "body{font:16px/1.5 system-ui;color:#18332e;max-width:850px;margin:2rem auto;padding:1rem}"
             "h1,h2,h3{line-height:1.2}section{break-inside:avoid}li{margin:.5rem 0}"
             "details{border-top:1px solid #bbb;margin-top:2rem;padding-top:1rem}"
             "@media print{body{font-size:11pt;margin:0}details{break-before:page}}",
             "</style><body><main><p>SurveyCoach · Share for sign-off · not launch approval</p>",
             f"<h1>{text(detail['title'])}</h1><p>Round {detail['version']}</p>",
             f"<h2>{text(summary['verdict'])}</h2>",
             f"<p>About {minutes} minutes for members (estimate).</p>",
             f"<p><strong>What we checked:</strong> {text(summary['scope']['summary'])}</p>"]
    parts.extend(f"<p>{text(line)}</p>" for line in summary["scope"]["unchecked_paths"])
    parts.append("<p>Keep mine acknowledges a risk; it is not evidence that an issue was corrected. "
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
                parts.append(f"<p>Find: {text(line['find'])}<br>Replace: {text(line['replace'])}</p>")
                if line.get("manual_edit_required"):
                    parts.append("<p>Review the source manually; this change is not a verified text replacement.</p>")
            else:
                parts.append(f"<p>{text(line['find'])}<br>Reason: {text(line['reason'])} (acknowledged risk)</p>")
            parts.append("</li>")
        parts.append("</ul></section>")
    changes = detail.get("round_changes", {})
    parts.append("<section><h2>What changed since the previous round</h2>")
    if not changes.get("compared_to_round"):
        parts.append("<p>First round: no previous comparison.</p>")
    else:
        parts.append(f"<p>Compared with Round {text(changes['compared_to_round'])}: "
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
