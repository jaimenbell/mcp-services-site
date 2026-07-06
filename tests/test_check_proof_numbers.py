"""Tests for scripts/check_proof_numbers.py.

Uses only temp fixtures (tmp_path) -- never touches the real site content files
(index.html, GO-LIVE.md, case-studies/*.html), per the lane contract's rule that
tests must not mutate real site files.
"""

import sys
from pathlib import Path

import pytest

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


def test_labelled_number_with_intervening_word_is_detected(tmp_path):
    """Reviewer finding 2 repro: 'mcp-factory ships with 200 unit tests' --
    number-before-label with one intervening word between them. Previously
    invisible (zero findings, not even WARN) because PATTERN_LABELLED only
    matched NUM directly adjacent to the label word."""
    manifest = {"mcp-factory": 187}
    f = write(
        tmp_path,
        "mcp-factory.html",
        "<p>mcp-factory ships with 200 unit tests, public repo.</p>\n",
    )
    findings = cpn.scan_file(f, manifest)
    assert findings, "the 200 citation must be detected, not silently invisible"
    fails = [x for x in findings if x.verdict == "FAIL" and x.number == 200]
    assert len(fails) == 1
    assert fails[0].expected == 187


def test_labelled_number_reversed_label_before_number_with_colon(tmp_path):
    """Reviewer finding 2 repro: 'tests passing: 200' -- label before number,
    separated by a colon."""
    manifest = {"mcp-factory": 187}
    f = write(
        tmp_path,
        "mcp-factory.html",
        "<p>mcp-factory: tests passing: 200</p>\n",
    )
    findings = cpn.scan_file(f, manifest)
    assert findings, "the 200 citation must be detected, not silently invisible"
    fails = [x for x in findings if x.verdict == "FAIL" and x.number == 200]
    assert len(fails) == 1
    assert fails[0].expected == 187


def test_labelled_number_reversed_label_colon_number_bare(tmp_path):
    """Reviewer finding 2 repro: 'tests: 200' -- bare label-before-number."""
    manifest = {"mcp-factory": 187}
    f = write(
        tmp_path,
        "mcp-factory.html",
        "<p>mcp-factory tests: 200</p>\n",
    )
    findings = cpn.scan_file(f, manifest)
    assert findings, "the 200 citation must be detected, not silently invisible"
    fails = [x for x in findings if x.verdict == "FAIL" and x.number == 200]
    assert len(fails) == 1
    assert fails[0].expected == 187


def test_labelled_number_hyphenated_n_test(tmp_path):
    """Reviewer finding 2 repro: '200-test suite' -- hyphenated N-test."""
    manifest = {"mcp-factory": 187}
    f = write(
        tmp_path,
        "mcp-factory.html",
        "<p>mcp-factory ships a 200-test suite, public repo.</p>\n",
    )
    findings = cpn.scan_file(f, manifest)
    assert findings, "the 200 citation must be detected, not silently invisible"
    fails = [x for x in findings if x.verdict == "FAIL" and x.number == 200]
    assert len(fails) == 1
    assert fails[0].expected == 187


def test_manifest_typo_field_exits_2_not_silent_pass(tmp_path):
    """Reviewer finding 3 repro: a typo'd field name (`Value = 187` instead of
    `value = 187`) must NOT make load_manifest() silently return {} (which
    would turn every FAIL into an unresolved WARN and still exit 0). Loading
    a malformed manifest must fail closed: print an error and raise, so
    run()/main() can exit 2 instead of silently passing."""
    manifest_toml = tmp_path / "proof-manifest.toml"
    manifest_toml.write_text(
        '["mcp-factory"]\n'
        'Value = 187\n'  # typo: capital V -- schema requires lowercase "value"
        'source_cmd = "pytest -q"\n',
        encoding="utf-8",
    )
    with pytest.raises(cpn.ManifestValidationError):
        cpn.load_manifest(manifest_toml)


def test_manifest_missing_source_cmd_exits_2_not_silent_pass(tmp_path):
    """A section with `value` but no `source_cmd` is equally malformed per
    the schema (every section MUST contribute both) and must fail closed."""
    manifest_toml = tmp_path / "proof-manifest.toml"
    manifest_toml.write_text(
        '["mcp-factory"]\nvalue = 187\n',
        encoding="utf-8",
    )
    with pytest.raises(cpn.ManifestValidationError):
        cpn.load_manifest(manifest_toml)


def test_manifest_typo_field_run_exits_2(tmp_path):
    """End-to-end: run() against a malformed manifest exits 2 (fail-closed),
    never silently exits 0 with every citation demoted to WARN."""
    manifest_toml = tmp_path / "proof-manifest.toml"
    manifest_toml.write_text(
        '["mcp-factory"]\nValue = 187\nsource_cmd = "pytest -q"\n',
        encoding="utf-8",
    )
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    write(site_dir, "index.html", "<p>mcp-factory: 179 passing tests</p>\n")
    exit_code = cpn.run(root=site_dir, manifest_path=manifest_toml, target_patterns=["*.html"])
    assert exit_code == 2


def test_default_target_globs_cover_articles_scoreboard_404(tmp_path):
    """Reviewer finding 6 repro: the pre-commit hook invokes this script with
    no argv, so it relies entirely on DEFAULT_TARGET_GLOBS. That list omitted
    articles/*.html, scoreboard.html, and 404.html -- a stale proof number
    committed in any of those files would never be scanned at all."""
    manifest_toml = tmp_path / "proof-manifest.toml"
    manifest_toml.write_text(
        '["mcp-factory"]\nvalue = 187\nsource_cmd = "pytest -q"\n',
        encoding="utf-8",
    )
    site_dir = tmp_path / "site"
    (site_dir / "articles").mkdir(parents=True)
    write(site_dir, "scoreboard.html", "<p>mcp-factory: 179 passing tests</p>\n")
    write(site_dir, "404.html", "<p>mcp-factory: 179 passing tests</p>\n")
    write(site_dir / "articles", "post.html", "<p>mcp-factory: 179 passing tests</p>\n")

    exit_code = cpn.run(root=site_dir, manifest_path=manifest_toml)
    assert exit_code == 2, (
        "a stale number in articles/*.html, scoreboard.html, or 404.html must "
        "be caught by the default (no-argv) scan the pre-commit hook uses"
    )


def test_verb_usage_of_tests_is_not_a_proof_number_citation(tmp_path):
    """Regression for a real false-positive surfaced by widening
    DEFAULT_TARGET_GLOBS to scoreboard.html (finding 6) combined with the
    finding-1 by-value-fallback hardening: scoreboard.html:501 reads 'Wave 7
    tests whether this collapses into news_veto...' -- "tests" used as a
    VERB (Wave 7 [subject] tests [verb] whether...), not a test-count noun.
    This must never be treated as a proof-number citation at all."""
    manifest = {"mcp-factory": 187}
    f = write(
        tmp_path,
        "scoreboard.html",
        '<td class="sb-notes">LIKELY-REDUNDANT hint; Wave 7 tests whether '
        "this collapses into news_veto with no independent lift</td>\n",
    )
    findings = cpn.scan_file(f, manifest)
    assert findings == [], f"'Wave 7 tests whether...' must not be flagged at all: {[x.format() for x in findings]}"


def test_run_end_to_end_exit_codes(tmp_path):
    """run() against a tmp root: clean fixture -> exit 0, stale fixture -> exit 2."""
    manifest_toml = tmp_path / "proof-manifest.toml"
    manifest_toml.write_text(
        '["mcp-factory"]\nvalue = 187\nsource_cmd = "pytest -q"\n',
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
