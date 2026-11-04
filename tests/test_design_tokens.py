"""Part B foundation contract: exact palette, contrast and token-only styling."""
import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
CSS = (SITE / "design-system.css").read_text()
PALETTE = dict(zip(
    "bg surface surface-2 line line-strong text muted accent accent-soft on-accent "
    "critical critical-soft attention attention-soft positive positive-soft mark "
    "zone-fresh zone-builds zone-high phone-bg phone-text phone-frame".split(),
    "#F7F8FA #FFFFFF #F1F4F8 #E3E8EF #74859A #0F1B2D #5B6B80 #0067A0 #E6F1F8 #FFFFFF "
    "#B42318 #FEF3F2 #B54708 #FFFAEB #067647 #ECFDF3 #FFF1B8 "
    "#B9D9EC #F6D28B #F2A99F #FFFFFF #1D2939 #0F1B2D".split(),
))
TEXT_PAIRS = [("text", "bg"), ("text", "surface"), ("muted", "surface"),
              ("muted", "bg"), ("muted", "surface-2"), ("accent", "surface"),
              ("on-accent", "accent"), ("accent", "accent-soft"),
              ("critical", "critical-soft"), ("attention", "attention-soft"),
              ("positive", "positive-soft")]


def token(name):
    match = re.search(rf"--{name}:\s*(#[0-9A-Fa-f]{{6}})\b", CSS)
    assert match, f"Missing literal foundation token: {name}"
    return match.group(1).upper()


def lum(value):
    channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    channels = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in channels]
    return sum(c * weight for c, weight in zip(channels, (.2126, .7152, .0722)))


def contrast(fg, bg):
    hi, lo = sorted((lum(token(fg)), lum(token(bg))), reverse=True)
    return (hi + .05) / (lo + .05)


def test_exact_foundation_palette():
    assert {name: token(name) for name in PALETTE} == PALETTE


def test_text_pairs_meet_aa():
    for fg, bg in TEXT_PAIRS:
        assert contrast(fg, bg) >= 4.5, (fg, bg)


def test_control_boundaries_meet_3_to_1():
    for bg in ("surface", "bg"):
        assert contrast("line-strong", bg) >= 3


def test_colour_lives_only_in_tokens():
    for css in SITE.glob("*.css"):
        if css.name != "design-system.css":
            assert not re.search(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(|hsla?\(", css.read_text()), css.name


def test_no_decorative_gradients_or_glass():
    for css in SITE.glob("*.css"):
        assert not re.search(r"(?:radial|linear)-gradient|backdrop-filter", css.read_text()), css.name


def test_all_css_token_references_resolve():
    styles = "\n".join(css.read_text() for css in SITE.glob("*.css"))
    defined = set(re.findall(r"(--[\w-]+)\s*:", styles)) | {"--e", "--k"}
    assert set(re.findall(r"var\((--[\w-]+)", styles)) <= defined
