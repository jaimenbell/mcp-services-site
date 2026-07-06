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
