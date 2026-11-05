"""Images that work on a phone (7.2 7.3 7.5 7.6) and members who can't see an image (B7)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from surveycoach.checks.registry import (Problem, ReviewContext, blocker_ok, check, finding, not_applicable, passed,
                                         problem_finding, result, share_fraction)
from surveycoach.findings import CheckResult, Finding
from surveycoach.imageio import BLUR_MIN, analyze_image
from surveycoach.snapshot import Media

FULL_WIDTH_CSS_PX = 300          # an image this wide fills a phone
MIN_FULL_WIDTH_PIXELS = 750      # rubric 7.3
MIN_DENSITY = 2                  # file pixels per CSS pixel; phones are 2x to 3x
MAX_IMAGE_BYTES = 500_000        # rubric 7.6
MAX_SURVEY_BYTES = 5_000_000
MAX_IMAGE_CHOICES = 6
TOO_SMALL_CSS_PX = 100
PORTRAIT_MIN, SQUARE_MAX, MILD_LANDSCAPE_MAX = 0.8, 1.0, 4 / 3
EPS = 1e-9


@dataclass(frozen=True)
class MediaRef:
    media: Media
    page_id: str
    question_id: str | None
    in_image_choice: bool


def all_media(ctx: ReviewContext) -> list[MediaRef]:
    refs = []
    for page in ctx.snapshot.pages:
        refs += [MediaRef(m, page.id, None, False) for m in page.media]
        for q in page.questions:
            refs += [MediaRef(m, page.id, q.id, False) for m in q.media]
            refs += [MediaRef(o.media, page.id, q.id, q.kind == "image_choice") for o in q.options if o.media]
    return [r for r in refs if r.media.kind == "image"]


def _ratio(m: Media) -> float | None:
    if not m.loaded:
        return None  # A failed image's rendered box does not establish source shape.
    w, h = (m.natural_w, m.natural_h) if m.natural_w and m.natural_h else (m.rendered_w, m.rendered_h)
    return w / h if w and h else None


def _label(ref: MediaRef) -> str:
    return (ref.media.alt or "").strip() or ref.media.element_id or "an image"


def _img_finding(criterion: str, ref: MediaRef, problem: Problem, impact: str) -> Finding:
    return problem_finding(criterion, problem, impact, page_id=ref.page_id, question_id=ref.question_id,
                           element_id=ref.media.element_id or None)


@check("7.2")
def phone_friendly_shape(ctx: ReviewContext) -> CheckResult:
    worst, worst_ref, worst_ratio = 1.0, None, None
    for ref in all_media(ctx):
        ratio = _ratio(ref.media)
        if ratio is None:
            continue
        if PORTRAIT_MIN - EPS <= ratio <= SQUARE_MAX + EPS:
            fraction = 1.0
        elif ratio > MILD_LANDSCAPE_MAX:
            fraction = 0.0
        else:
            fraction = 1 / 3
        if fraction < worst:
            worst, worst_ref, worst_ratio = fraction, ref, ratio
    if worst_ref is None:
        return passed("7.2") if any(_ratio(r.media) for r in all_media(ctx)) else not_applicable("7.2")
    shape = "wide" if worst_ratio > 1 else "tall"
    return result("7.2", worst, _img_finding("7.2", worst_ref, Problem(
        f"Check {shape} image on mobile: potential layout risk", f"A {shape} image ({worst_ratio:.2f} wide for every 1 tall).",
        "Open the actual survey on a mobile device. Check that the full image is readable, not cropped, stretched or too small. "
        "Orientation alone does not prove a broken layout. Adjust placement or size only if needed; preserve research content."),
        "Desktop drafting can hide small image details or awkward image composition on a phone."))


def _sharpness_problems(ref: MediaRef) -> list[Problem]:
    m, problems = ref.media, []
    if m.natural_w and m.rendered_w:
        if m.rendered_w >= FULL_WIDTH_CSS_PX and m.natural_w < MIN_FULL_WIDTH_PIXELS:
            problems.append(Problem("Image is too small to show full width", f"{m.natural_w} px wide, shown full width.",
                                    f"Use the original file, at least {MIN_FULL_WIDTH_PIXELS} px wide. Never upscale a small one."))
        elif m.natural_w < m.rendered_w * MIN_DENSITY:
            problems.append(Problem("Image will look soft on sharp phone screens", f"{m.natural_w} px wide, shown at {m.rendered_w} px.",
                                    "Use a larger original so it stays crisp on high-density phone screens."))
    if m.natural_w and m.natural_h and m.rendered_w and m.rendered_h and m.object_fit not in {"cover", "contain", "scale-down"}:
        drift = abs(m.natural_w / m.natural_h - m.rendered_w / m.rendered_h) / (m.natural_w / m.natural_h)
        if drift > 0.05:
            problems.append(Problem("Image is stretched or squashed", "The image is stretched or squashed.",
                                    "Show it at its natural shape, or crop it deliberately."))
    if m.asset_path and Path(m.asset_path).exists() and analyze_image(m.asset_path).blur_score < BLUR_MIN:
        problems.append(Problem("Image looks blurry", "The image looks blurry.", "Replace it with a sharper original photo."))
    return problems


@check("7.3")
def sharp_and_high_res(ctx: ReviewContext) -> CheckResult:
    refs = [r for r in all_media(ctx) if r.media.loaded]
    if not refs:
        return not_applicable("7.3")
    findings, failing = [], 0
    for ref in refs:
        problems = _sharpness_problems(ref)
        failing += bool(problems)
        findings += [_img_finding("7.3", ref, pr, "Soft or stretched images make products look cheap and hard to judge.")
                     for pr in problems]
    return result("7.3", share_fraction(failing, len(refs)), *findings)


@check("7.5")
def fair_image_choices(ctx: ReviewContext) -> CheckResult:
    questions = [q for q in ctx.snapshot.all_questions() if sum(1 for o in q.options if o.media) >= 2]
    if not questions:
        return not_applicable("7.5")
    findings, failing = [], 0
    for q in questions:
        pictured = [o for o in q.options if o.media]
        ratios = [r for o in pictured if (r := _ratio(o.media))]
        widths = [o.media.natural_w for o in pictured if o.media.natural_w]
        problems = []
        if ratios and max(ratios) / min(ratios) > 1.05:
            problems.append(Problem("Image options have different shapes", "The images have different shapes.",
                                    "Crop every option to the same shape."))
        if widths and max(widths) / min(widths) > 1.25:
            problems.append(Problem("Image options differ a lot in size", "The images are very different sizes.",
                                    "Use matching sizes so no option looks fancier."))
        if any(not o.label.strip() for o in pictured):
            problems.append(Problem("Image option has no label", "Some options have no label.", "Give every image a short label."))
        if len(pictured) > MAX_IMAGE_CHOICES:
            problems.append(Problem(f"{len(pictured)} image options; use {MAX_IMAGE_CHOICES}", f"{len(pictured)} image options.",
                                    f"Use {MAX_IMAGE_CHOICES} or fewer."))
        failing += bool(problems)
        findings += [problem_finding("7.5", pr, "Unequal images bias the result: the prettiest photo wins.",
                                     question_id=q.id) for pr in problems]
    return result("7.5", share_fraction(failing, len(questions)), *findings)


@check("7.6")
def light_and_accessible(ctx: ReviewContext) -> CheckResult:
    refs = all_media(ctx)
    if not refs:
        return not_applicable("7.6")
    findings, failing = [], 0
    for ref in refs:
        problems = []
        if (ref.media.bytes or 0) > MAX_IMAGE_BYTES:
            problems.append(Problem(f"Image file is heavy ({ref.media.bytes // 1000} KB)", f"{ref.media.bytes // 1000} KB image.",
                                    "Compress it to under about 500 KB."))
        if ref.media.role != "decoration" and not (ref.media.alt or "").strip():
            problems.append(Problem("Image has no alt text", "An image has no alt text.",
                                    "Add a short description for screen readers."))
        failing += bool(problems)
        findings += [_img_finding("7.6", ref, pr, "Heavy images are slow on cellular, and members using screen readers lose context.")
                     for pr in problems]
    total_bytes = sum(r.media.bytes or 0 for r in refs)
    heavy = total_bytes > MAX_SURVEY_BYTES
    if heavy:
        findings.append(finding("7.6", "worth_improving", f"Images total {total_bytes / 1_000_000:.1f} MB; keep under 5",
                                f"Images total {total_bytes / 1_000_000:.1f} MB.",
                                "Keep the whole survey under about 5 MB of images.",
                                "Many members are on cellular, where big surveys load slowly."))
    return result("7.6", share_fraction(failing + heavy, len(refs) + 1), *findings)


@check("B7")
def cannot_see_image(ctx: ReviewContext) -> CheckResult:
    findings = []
    for ref in all_media(ctx):
        broken = not ref.media.loaded
        tiny = ref.in_image_choice and ref.media.rendered_w is not None and ref.media.rendered_w < TOO_SMALL_CSS_PX
        if broken or tiny:
            findings.append(finding(
                "B7", "worth_improving" if broken else "must_fix",
                f"Reader could not verify image loading: {_label(ref)}" if broken else f"Image options are too small to judge ({ref.media.rendered_w} px)",
                f'The reader observed an unloaded image: "{_label(ref)}". The cause was not measured.' if broken else f"An image is only {ref.media.rendered_w} px wide.",
                "Open this screen in the actual survey on a phone. If the image also fails there, check its link and re-upload it. "
                "If it loads slowly, try a smaller file while keeping text and details readable. "
                "If it works there, report a reader capture issue; this observation does not establish a network or file-size problem." if broken
                else "Show the images larger, at least 2 per row, so members can judge them.",
                "If members cannot see an image, they may lack information needed to answer; a reader-only failure does not prove that." if broken
                else "Members need readable image choices to make an informed selection.",
                page_id=ref.page_id, question_id=ref.question_id, element_id=ref.media.element_id or None))
    if findings:
        return CheckResult(criterion_id="B7", findings=findings,
                           assessed=not any(not ref.media.loaded for ref in all_media(ctx)))
    return blocker_ok("B7")
