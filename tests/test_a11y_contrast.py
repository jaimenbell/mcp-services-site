"""Contrast guard for the `--faint` token (WCAG 1.4.3, 4.5:1 for normal text).

Why this file exists
--------------------
`--faint` is the dimmest text token on the site, so it is the only one that
lands anywhere near the 4.5:1 floor. It is defined TWICE, in two stylesheets
that are never loaded together:

  * css/style.css  -- linked by 26 pages (404, articles/, case-studies/,
    managed-watch, scoreboard). Palette: blue accent #5b9dff.
  * index.html     -- links NO stylesheet at all; it carries a complete inline
    <style> with its own palette (teal accent #5eead4).

They are two parallel palettes on disjoint page sets, NOT a cascade conflict:
no page ever sees both definitions. Collapsing them to one value is therefore
out of scope here -- each is checked against its OWN backgrounds.

The historical finding recorded `--faint` at "4.53:1", which is the css/style.css
value measured against `--bg` only. That surface passed; the CARD surfaces did
not (4.02:1 on --card, 4.22:1 on --bg-soft). This test measures every surface
the token is actually used on, so a partial measurement cannot pass again.

SCOPE (stated with the pattern, deliberately): normal-size body text only.
index.html's `.deco` also uses var(--faint) but at `opacity: .26` and under
`aria-hidden="true"` -- decorative text, exempt from 1.4.3, and excluded here
on purpose rather than by omission.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STYLE_CSS = REPO_ROOT / "css" / "style.css"
INDEX_HTML = REPO_ROOT / "index.html"

WCAG_AA_NORMAL_TEXT = 4.5


def _relative_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    channels = []
    for i in (0, 2, 4):
        c = int(h[i : i + 2], 16) / 255.0
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    a, b = _relative_luminance(fg), _relative_luminance(bg)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def _token(source: str, name: str) -> str:
    """Read a `--name: #rrggbb;` custom property out of a stylesheet source."""
    m = re.search(r"^\s*--" + re.escape(name) + r":\s*(#[0-9a-fA-F]{6});", source, re.M)
    assert m, f"token --{name} not found -- did the palette change shape?"
    return m.group(1).lower()


def _read(path: Path) -> str:
    return io.open(path, encoding="utf-8").read()


# --- positive control: the check must FIRE on known-bad and STAY SILENT on known-good ---


def test_positive_control_ratio_math_matches_known_values():
    # Black on white is the textbook maximum.
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
    # Identical colors are the textbook minimum.
    assert contrast_ratio("#151c2c", "#151c2c") == pytest.approx(1.0, abs=0.001)


def test_positive_control_fires_on_the_exact_historical_failure():
    """The pre-fix value on the card surface. If this ever stops failing, the
    guard below has become incapable of failing and is a lie with a green light."""
    ratio = contrast_ratio("#6b7c98", "#151c2c")
    assert ratio == pytest.approx(4.02, abs=0.01)
    assert ratio < WCAG_AA_NORMAL_TEXT


def test_positive_control_stays_silent_on_a_known_good_pair():
    assert contrast_ratio("#9fb0c9", "#151c2c") >= WCAG_AA_NORMAL_TEXT


# --- the real guard, against the checked-in stylesheets ---

# Surfaces --faint text is actually painted on, derived from the stylesheet:
#   --bg       body background (footer.site, article.cs .meta, .sb-* notes)
#   --bg-soft  .step / article.cs .evidence / article.cs pre
#   --card     .tier (.tier .price small) / .card / .case / .faq details
STYLE_CSS_SURFACES = ("bg", "bg-soft", "card")

# index.html's own palette. Lightest surface --faint can sit on is --panel-2.
INDEX_SURFACES = ("bg", "bg-2", "panel", "panel-2")


@pytest.mark.parametrize("surface", STYLE_CSS_SURFACES)
def test_style_css_faint_meets_aa_on_every_surface_it_is_used_on(surface):
    src = _read(STYLE_CSS)
    faint = _token(src, "faint")
    bg = _token(src, surface)
    ratio = contrast_ratio(faint, bg)
    assert ratio >= WCAG_AA_NORMAL_TEXT, (
        f"css/style.css --faint {faint} on --{surface} {bg} is {ratio:.2f}:1, "
        f"below the {WCAG_AA_NORMAL_TEXT}:1 floor for normal text"
    )


@pytest.mark.parametrize("surface", INDEX_SURFACES)
def test_index_html_faint_meets_aa_on_every_surface_it_is_used_on(surface):
    src = _read(INDEX_HTML)
    faint = _token(src, "faint")
    bg = _token(src, surface)
    ratio = contrast_ratio(faint, bg)
    assert ratio >= WCAG_AA_NORMAL_TEXT, (
        f"index.html --faint {faint} on --{surface} {bg} is {ratio:.2f}:1, "
        f"below the {WCAG_AA_NORMAL_TEXT}:1 floor for normal text"
    )


def test_the_two_faint_definitions_are_still_on_disjoint_page_sets():
    """The premise the scoping above rests on. index.html linking css/style.css
    would turn two independent palettes into a real cascade conflict, and the
    per-file checks above would no longer describe what renders."""
    assert "css/style.css" not in _read(INDEX_HTML)
