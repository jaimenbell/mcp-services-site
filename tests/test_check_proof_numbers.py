"""Tests for scripts/check_proof_numbers.py.

Uses only temp fixtures (tmp_path) -- never touches the real site content files
(index.html, GO-LIVE.md, case-studies/*.html), per the lane contract's rule that
tests must not mutate real site files.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_proof_numbers as cpn  # noqa: E402


def write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_manifest_matching_number_passes(tmp_path):
    """A citation that matches the manifest value produces no FAIL finding."""
    manifest = {"mcp-factory": 187}
    f = write(
        tmp_path,
        "case-study.html",
        '<span class="pill">187 passing tests</span>\n'
        "<p>mcp-factory ships with 187 passing tests, public repo.</p>\n",
    )
    findings = cpn.scan_file(f, manifest)
    fails = [x for x in findings if x.verdict == "FAIL"]
    assert fails == []


def test_stale_number_fails_with_file_line_and_expected_found(tmp_path):
    """A citation that contradicts the manifest fails, reporting file:line + expected/found."""
    manifest = {"mcp-factory": 187}
    f = write(
        tmp_path,
        "mcp-factory.html",
        "line one is a spacer\n"
        "<p>mcp-factory ships with 179 passing tests, public repo.</p>\n",
    )
    findings = cpn.scan_file(f, manifest)
    fails = [x for x in findings if x.verdict == "FAIL"]
    assert len(fails) == 1
    finding = fails[0]
    assert finding.line_no == 2
    assert finding.number == 179
    assert finding.expected == 187
    assert finding.repo_key == "mcp-factory"
    rendered = finding.format()
    assert "179" in rendered and "187" in rendered
    assert f"{f}:2" in rendered or ":2:" in rendered


def test_unknown_number_warns_not_fails(tmp_path):
    """A test-count citation with no corresponding manifest entry WARNs, never fails."""
    manifest = {"mcp-factory": 187}
    f = write(
        tmp_path,
        "honest-harness.html",
        '<span class="pill">186 tests (options-bot)</span>\n',
    )
    findings = cpn.scan_file(f, manifest)
    fails = [x for x in findings if x.verdict == "FAIL"]
    warns = [x for x in findings if x.verdict == "WARN"]
    assert fails == []
    assert len(warns) == 1
    assert warns[0].number == 186


def test_no_false_positive_on_incidental_integers(tmp_path):
    """Prices, years, tool counts, and IDs near (but not adjacent to) 'test'
    words must never be flagged -- only numbers directly labelled by a
    test/passing/passed word are candidates."""
    manifest = {"mcp-factory": 187, "desktop-mcp": 121}
    f = write(
        tmp_path,
        "desktop-mcp.html",
        # "18 tools" must not be compared against the desktop-mcp value (121)
        # even though the line also contains the trigger word "passing".
        '<div class="meta">// public repo . 18 tools . 121 passing tests . input off by default</div>\n'
        # incidental integers with no trigger word anywhere on the line
        "<p>Priced from $2,500. Copyright 2026. Order #4092.</p>\n",
    )
    findings = cpn.scan_file(f, manifest)
    numbers_seen = {x.number for x in findings}
    assert 18 not in numbers_seen
    assert 2500 not in numbers_seen
    assert 2026 not in numbers_seen
    assert 4092 not in numbers_seen
    # 121 should have been seen and matched cleanly (no FAIL, since it's correct)
    fails = [x for x in findings if x.verdict == "FAIL"]
    assert fails == []


def test_roster_idiom_pairs_numbers_with_repo_slugs(tmp_path):
    """The 'Test counts (179 mcp-factory, 50 rag-mcp, 186 options-bot)' idiom
    is parsed into independent (number, repo) pairs."""
    manifest = {"mcp-factory": 187, "rag-mcp": 51}
    f = write(
        tmp_path,
        "GO-LIVE.md",
        "Test counts (179 mcp-factory, 50 rag-mcp, 186 options-bot) were live-verified today\n",
    )
    findings = cpn.scan_file(f, manifest)
    fails = {x.repo_key: x for x in findings if x.verdict == "FAIL"}
    warns = {x.repo_key: x for x in findings if x.verdict == "WARN"}
    assert fails["mcp-factory"].number == 179
    assert fails["mcp-factory"].expected == 187
    assert fails["rag-mcp"].number == 50
    assert fails["rag-mcp"].expected == 51
    assert "options-bot" in warns


def test_deco_span_bare_numbers_are_checked_by_value_when_correct(tmp_path):
    """Reviewer finding 1 repro: index.html:897's decorative span cites
    '187 passing / 74 tests / 121 tests' with NO repo label within the
    10-line window (unlike the proof-card blocks, which sit far below).
    When the bare numbers match manifest values exactly, they must be
    associated by value and pass silently -- not WARN as unassociated."""
    manifest = {"mcp-factory": 187, "github-mcp": 74, "desktop-mcp": 121}
    f = write(
        tmp_path,
        "index.html",
        '<span class="deco"><span class="n">check</span> 187 passing<br>'
        '<span class="n">check</span> 74 tests<br>'
        '<span class="n">check</span> 121 tests</span>\n',
    )
    findings = cpn.scan_file(f, manifest)
    fails = [x for x in findings if x.verdict == "FAIL"]
    warns = [x for x in findings if x.verdict == "WARN"]
    assert fails == []
    # These numbers must be resolved (associated by value), not left as
    # unassociated WARNs -- the whole point of the fix.
    assert warns == []
    repo_keys_seen = {x.repo_key for x in findings}
    assert repo_keys_seen <= {"mcp-factory", "github-mcp", "desktop-mcp"}


def test_deco_span_bare_numbers_fail_when_manifest_value_mutated(tmp_path):
    """Acceptance bar for finding 1: mutate mcp-factory's manifest value and
    confirm the 897-style span (and meta-tag-style citation) now FAIL instead
    of silently passing/warning."""
    manifest = {"mcp-factory": 200, "github-mcp": 74, "desktop-mcp": 121}
    f = write(
        tmp_path,
        "index.html",
        '<span class="deco"><span class="n">check</span> 187 passing<br>'
        '<span class="n">check</span> 74 tests<br>'
        '<span class="n">check</span> 121 tests</span>\n',
    )
    findings = cpn.scan_file(f, manifest)
    fails = [x for x in findings if x.verdict == "FAIL"]
    assert len(fails) == 1
    assert fails[0].number == 187


def test_meta_description_bare_number_fails_when_manifest_value_mutated(tmp_path):
    """Same repro as above but for the og:/twitter:description meta-tag style
    citation (index.html:15,23): a single bare number, far from any proof
    card, in a one-line file where no manifest key appears anywhere."""
    manifest = {"mcp-factory": 200}
    f = write(
        tmp_path,
        "index.html",
        '<meta property="og:description" content="Public proof: 187 passing tests." />\n',
    )
    findings = cpn.scan_file(f, manifest)
    fails = [x for x in findings if x.verdict == "FAIL"]
    assert len(fails) == 1
    assert fails[0].number == 187


def test_known_noncanonical_orphaned_number_still_warns_not_fails(tmp_path):
    """Guardrail: numbers that are legitimately cited in test-count context but
    do not correspond to any manifest-tracked repo (the options-bot 186, the
    fleet-reliability-day composite 2806/283) must remain WARN, never FAIL --
    the by-value hardening must not false-positive on these."""
    manifest = {"mcp-factory": 187}
    assert cpn.KNOWN_NONCANONICAL_NUMBERS, "fixture assumes a non-empty allowlist"
    for number in sorted(cpn.KNOWN_NONCANONICAL_NUMBERS):
        f = write(
            tmp_path,
            f"noncanonical-{number}.html",
            f'<span class="pill">{number} tests (some-untracked-thing)</span>\n',
        )
        findings = cpn.scan_file(f, manifest)
        fails = [x for x in findings if x.verdict == "FAIL"]
        assert fails == [], f"{number} should WARN, not FAIL: {[x.format() for x in findings]}"


def test_orphaned_unknown_number_in_test_context_fails_as_suspicious(tmp_path):
    """A number that matches NO manifest value and is not in the documented
    known-non-canonical allowlist, cited in a test-count context with no
    nearby repo label, is presumed a drifted/uncanonical proof-number citation
    and must FAIL rather than silently WARN."""
    manifest = {"mcp-factory": 187}
    assert 999983 not in cpn.KNOWN_NONCANONICAL_NUMBERS
    f = write(
        tmp_path,
        "orphaned.html",
        '<span class="pill">999983 passing tests</span>\n',
    )
    findings = cpn.scan_file(f, manifest)
    fails = [x for x in findings if x.verdict == "FAIL"]
    assert len(fails) == 1
    assert fails[0].number == 999983


def test_run_end_to_end_exit_codes(tmp_path):
    """run() against a tmp root: clean fixture -> exit 0, stale fixture -> exit 2."""
    manifest_toml = tmp_path / "proof-manifest.toml"
    manifest_toml.write_text(
        '["mcp-factory"]\nvalue = 187\n',
        encoding="utf-8",
    )

    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    write(clean_dir, "index.html", "<p>mcp-factory: 187 passing tests</p>\n")
    exit_code = cpn.run(root=clean_dir, manifest_path=manifest_toml, target_patterns=["*.html"])
    assert exit_code == 0

    stale_dir = tmp_path / "stale"
    stale_dir.mkdir()
    write(stale_dir, "index.html", "<p>mcp-factory: 179 passing tests</p>\n")
    exit_code = cpn.run(root=stale_dir, manifest_path=manifest_toml, target_patterns=["*.html"])
    assert exit_code == 2
