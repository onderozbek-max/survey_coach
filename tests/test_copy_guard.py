"""Guard authored product copy; generated survey evidence is not product copy."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_CLAIMS = re.compile(
    r"actually finish|completion rate|drop-?off rate|will finish|guarantee|approved for launch|launch-ready",
    re.I,
)


class ForbiddenClaimError(AssertionError):
    """Only a completed scan finding forbidden copy may be expected to fail."""


def _copy_sources(root):
    html = sorted((root / "site").glob("*.html"))
    javascript = sorted(
        path for path in (root / "site").glob("*.js") if path.name != "data.js"
    )
    assert html, "No site HTML found: copy guard must not pass vacuously"
    assert javascript, "No authored site JavaScript found"
    return [
        *html,
        *javascript,
        root / "surveycoach/server/report.py",
        root / "surveycoach/signals.py",
    ]


def _find_claims(root):
    return [
        f"{path.relative_to(root)}:{line_number}: {match.group()}"
        for path in _copy_sources(root)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        for match in FORBIDDEN_CLAIMS.finditer(line)
    ]


@pytest.mark.xfail(
    strict=True,
    raises=ForbiddenClaimError,
    reason="Old local.html hero claims outcomes; remove in Part B Task 10 copy sweep",
)
def test_product_copy_does_not_claim_member_outcomes():
    claims = _find_claims(ROOT)
    if claims:
        raise ForbiddenClaimError("Forbidden product copy:\n" + "\n".join(claims))


@pytest.mark.parametrize(
    "source",
    ["site/local.html", "site/app.js", "surveycoach/server/report.py", "surveycoach/signals.py"],
)
def test_scan_covers_prescribed_sources_and_excludes_generated_data(tmp_path, source):
    for relative in (
        "site/local.html", "site/app.js", "surveycoach/server/report.py", "surveycoach/signals.py"
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Member experience estimate\n", encoding="utf-8")
    (tmp_path / "site/data.js").write_text("guarantee", encoding="utf-8")
    # A nested asset is outside the prescribed site/*.html and site/*.js scope.
    (tmp_path / "site/nested").mkdir()
    (tmp_path / "site/nested/ignored.js").write_text("guarantee", encoding="utf-8")
    assert _find_claims(tmp_path) == []

    phrases = [
        "ACTUALLY FINISH", "completion rate", "dropoff rate", "drop-off rate",
        "will finish", "guarantee", "approved for launch", "launch-ready",
    ]
    (tmp_path / source).write_text("\n".join(phrases), encoding="utf-8")
    assert _find_claims(tmp_path) == [
        f"{source}:{line_number}: {phrase}"
        for line_number, phrase in enumerate(phrases, 1)
    ]


def test_missing_site_sources_are_not_a_claim_failure(tmp_path):
    with pytest.raises(AssertionError, match="No site HTML found") as error:
        _find_claims(tmp_path)
    assert not isinstance(error.value, ForbiddenClaimError)


def test_missing_python_source_is_not_hidden_by_an_earlier_claim(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "local.html").write_text("actually finish", encoding="utf-8")
    (site / "app.js").write_text("", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        _find_claims(tmp_path)
