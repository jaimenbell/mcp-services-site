"""Parity guard between js/discord-cta.js's DISCORD_INVITE and the checked-in markup.

Why this file exists
--------------------
The Discord CTAs used to ship as `style="display:none"` in the markup, cleared
only by js/discord-cta.js. That meant a visitor with JavaScript disabled never
saw the homepage "join the build" band or the footer Discord link at all -- a
conversion defect, not only an accessibility one.

The naive fix (un-hide them from the <noscript> block) does NOT work: the
anchors also shipped with `href=""`, which resolves to the current page, so a
no-JS visitor would have seen a "Join the Discord" button that silently
reloads the page. The href has to be in the markup for the no-JS path to
function at all.

So the markup now ships visible, with the real invite URL, and the script
enforces the invariant in the other direction -- if DISCORD_INVITE is emptied,
it hides every CTA on load. That leaves exactly one residual risk: the JS
constant and the markup drifting apart, which no-JS visitors would experience
as a dead link. This test is the guard for that drift, in both directions:

  * invite NON-EMPTY -> every CTA wrapper must be visible in the markup and
    every anchor's href must equal the constant exactly.
  * invite EMPTY     -> every CTA wrapper must carry the inline display:none
    again, so the no-JS path cannot render a dead invite link.

Operator note: changing the invite URL now means editing js/discord-cta.js AND
the markup. This test tells you loudly which files you missed.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DISCORD_JS = REPO_ROOT / "js" / "discord-cta.js"

# Pins the exact checked-in declaration. If the line changes shape this stops
# matching and _invite() fails loudly rather than silently testing stale code.
INVITE_RE = re.compile(r'^var DISCORD_INVITE = "([^"]*)";', re.M)

WRAP_IDS = ("discord-cta", "discord-footer-link-wrap")
LINK_IDS = ("discord-cta-link", "discord-footer-link")


def _read(path: Path) -> str:
    return io.open(path, encoding="utf-8").read()


def _invite() -> str:
    m = INVITE_RE.search(_read(DISCORD_JS))
    assert m, "DISCORD_INVITE declaration not found in js/discord-cta.js"
    return m.group(1).strip()


def _pages():
    pages = sorted(
        set(REPO_ROOT.glob("*.html"))
        | set(REPO_ROOT.glob("articles/*.html"))
        | set(REPO_ROOT.glob("case-studies/*.html"))
    )
    assert pages, "no pages found -- glob is wrong"
    return pages


def _wrapper_tag(src: str, wrap_id: str):
    """The opening tag of the element with this id, or None if absent."""
    m = re.search(r"<[a-z]+[^>]*\bid=\"" + re.escape(wrap_id) + r"\"[^>]*>", src)
    return m.group(0) if m else None


def _href_for(src: str, link_id: str):
    m = re.search(
        r"<a[^>]*\bid=\"" + re.escape(link_id) + r"\"[^>]*>", src
    ) or re.search(r"<a[^>]*\bid=\"" + re.escape(link_id) + r"\"[^>]*>", src)
    if not m:
        return None
    h = re.search(r'\bhref="([^"]*)"', m.group(0))
    return h.group(1) if h else None


def _is_inline_hidden(tag: str) -> bool:
    return bool(re.search(r'style="[^"]*display:\s*none', tag, re.I))


# --- positive control: the drift detector must FIRE and STAY SILENT on demand ---


def test_positive_control_hidden_detector_fires_and_stays_silent():
    assert _is_inline_hidden('<span id="x" style="display:none">') is True
    assert _is_inline_hidden('<span id="x" style="display: none">') is True
    assert _is_inline_hidden('<span id="x">') is False
    assert _is_inline_hidden('<span id="x" style="color:red">') is False


def test_positive_control_href_extraction_fires_on_the_exact_historical_defect():
    """`href=""` is the pre-fix state: an anchor that reloads the current page."""
    bad = '<a id="discord-footer-link" href="" target="_blank" rel="noopener">'
    good = '<a id="discord-footer-link" href="https://discord.gg/abc" rel="noopener">'
    assert _href_for(bad, "discord-footer-link") == ""
    assert _href_for(good, "discord-footer-link") == "https://discord.gg/abc"


# --- the real guard ---


def test_invite_constant_is_parseable():
    invite = _invite()
    assert invite == "" or invite.startswith("https://"), invite


@pytest.mark.parametrize("page", _pages(), ids=lambda p: p.name)
def test_markup_agrees_with_the_invite_constant(page: Path):
    src = _read(page)
    invite = _invite()

    for wrap_id, link_id in zip(WRAP_IDS, LINK_IDS):
        tag = _wrapper_tag(src, wrap_id)
        if tag is None:
            continue  # this page has no such CTA -- fine
        href = _href_for(src, link_id)
        assert href is not None, f"{page.name}: #{wrap_id} present but #{link_id} missing"

        if invite:
            assert not _is_inline_hidden(tag), (
                f"{page.name}: #{wrap_id} ships inline display:none while "
                f"DISCORD_INVITE is set -- no-JS visitors never see this CTA"
            )
            assert href == invite, (
                f"{page.name}: #{link_id} href is {href!r} but DISCORD_INVITE "
                f"is {invite!r} -- no-JS visitors would get the stale link"
            )
        else:
            assert _is_inline_hidden(tag), (
                f"{page.name}: DISCORD_INVITE is empty, so #{wrap_id} must ship "
                f"inline display:none or no-JS visitors see a dead invite link"
            )


SCOREBOARD_GENERATOR = REPO_ROOT / "scripts" / "generate-scoreboard.mjs"


def test_scoreboard_generator_template_matches_the_invite_constant():
    """scripts/generate-scoreboard.mjs full-overwrites scoreboard.html
    (fs.writeFileSync(OUT_HTML, ...)), so its inlined footer template is a
    PRODUCER for a page this suite also checks as an artifact. Without this
    test the next scoreboard regen would silently revert the no-JS fix on that
    one page, and the page-level check above would only notice afterwards."""
    src = _read(SCOREBOARD_GENERATOR)
    invite = _invite()
    tag = _wrapper_tag(src, "discord-footer-link-wrap")
    assert tag is not None, "generator no longer emits the Discord footer wrapper"
    href = _href_for(src, "discord-footer-link")
    if invite:
        assert not _is_inline_hidden(tag), (
            "generate-scoreboard.mjs still emits inline display:none -- a regen "
            "would re-hide the footer CTA from no-JS visitors"
        )
        assert href == invite, (
            f"generate-scoreboard.mjs emits href {href!r}, DISCORD_INVITE is "
            f"{invite!r} -- a regen would write a stale link into scoreboard.html"
        )
    else:
        assert _is_inline_hidden(tag)


def test_script_hides_ctas_when_the_invite_is_emptied():
    """The other half of the invariant lives in the JS, not the markup."""
    src = _read(DISCORD_JS)
    assert 'wrap.style.display = "none"' in src, (
        "js/discord-cta.js must actively hide the CTAs when DISCORD_INVITE is "
        "empty -- an early `return` would leave the now-visible markup showing "
        "a dead link"
    )


@pytest.mark.parametrize("page", _pages(), ids=lambda p: p.name)
def test_no_page_hides_anything_behind_a_js_only_inline_display_none(page: Path):
    """Broader sweep: the whole class of defect, not just the Discord CTAs.
    An inline display:none is only ever cleared by script, so anything wearing
    one is invisible on the no-JS path. If a future element legitimately needs
    one, it needs a <noscript> fallback too -- and an explicit exemption here."""
    src = _read(page)
    offenders = re.findall(r'<[^>]*style="[^"]*display:\s*none[^"]*"[^>]*>', src, re.I)
    assert not offenders, f"{page.name}: inline display:none on {offenders}"
