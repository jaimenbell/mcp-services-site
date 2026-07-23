"""Tests for scripts/check_proof_numbers.py.

Uses only temp fixtures (tmp_path) -- never touches the real site content files
(index.html, GO-LIVE.md, case-studies/*.html), per the lane contract's rule that
tests must not mutate real site files.
"""

import shutil
import subprocess
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


def _write_fake_runner(repo_dir: Path, passed_count: int, extra_py: str = "") -> None:
    """Write a tiny standalone script that mimics a pytest summary line, so
    live-check tests don't depend on any real sibling repo's suite/venv."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "fake_runner.py").write_text(
        f"{extra_py}\nprint('{passed_count} passed in 0.01s')\n",
        encoding="utf-8",
    )


def _fake_entry(repo_dir: Path, value: int) -> "cpn.ManifestEntry":
    return cpn.ManifestEntry(
        key="mcp-factory",
        value=value,
        source_cmd=f"{sys.executable} fake_runner.py",
        source_repo=str(repo_dir),
    )


def _write_junit_capable_fake_runner(
    repo_dir: Path, *, tests: int, failures: int = 0, errors: int = 0,
    skipped: int = 0, fake_summary_passed: int | None = None,
) -> None:
    """Write a fake runner that mimics the class of repo verified live
    2026-07-23 (github-mcp/desktop-mcp/rag-mcp/bus-mcp/discord-mcp/
    rails-mcp/vllm-ops-mcp): its plain -q summary line is fully suppressed
    under piped/non-tty capture (dots + "[100%]" only, zero "passed" text
    anywhere in stdout/stderr) -- but it DOES honor an appended
    --junitxml=<path> arg, same as real pytest. If fake_summary_passed is
    given, it ALSO prints a plain "N passed" line with that (possibly
    deliberately wrong) count, to prove which source wins when both are
    present."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    passed = tests - failures - errors - skipped
    summary_print = ""
    if fake_summary_passed is not None:
        summary_print = f'print("{fake_summary_passed} passed in 0.01s")\n'
    script = f'''
import sys
junit_path = None
for a in sys.argv[1:]:
    if a.startswith("--junitxml="):
        junit_path = a[len("--junitxml="):]
if junit_path:
    with open(junit_path, "w", encoding="utf-8") as fh:
        fh.write(
            "<?xml version='1.0' encoding='utf-8'?>"
            "<testsuites name='pytest tests'>"
            "<testsuite name='pytest' errors='{errors}' failures='{failures}' "
            "skipped='{skipped}' tests='{tests}' time='0.01'>"
            "</testsuite></testsuites>"
        )
print("." * {passed} + "             [100%]")
{summary_print}'''
    (repo_dir / "fake_runner.py").write_text(script, encoding="utf-8")


def _write_dots_only_fake_runner(repo_dir: Path, passed_count: int) -> None:
    """Fake runner that neither honors --junitxml nor prints a parseable
    summary line at all -- exercises the last-resort dot-count fallback."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "fake_runner.py").write_text(
        f'print("." * {passed_count} + "             [100%]")\n',
        encoding="utf-8",
    )


def test_live_check_mismatch_fails_with_clear_message(tmp_path):
    """Core fix: a manifest value that disagrees with the LIVE repo's actual
    test count must FAIL with a message naming both numbers and telling the
    operator to refresh the manifest AND the site citations -- this is the
    self-referential-gate bug the whole lane exists to close."""
    repo_dir = tmp_path / "mcp-factory"
    _write_fake_runner(repo_dir, passed_count=207)
    entries = {"mcp-factory": _fake_entry(repo_dir, value=199)}

    results = cpn.live_verify_manifest(entries)

    fails = [r for r in results if r.status == "FAIL"]
    assert len(fails) == 1
    assert fails[0].live_value == 207
    assert fails[0].expected == 199
    rendered = fails[0].format()
    assert "199" in rendered and "207" in rendered
    assert "stale" in rendered.lower()
    assert "manifest" in rendered.lower()


def test_live_check_agreement_passes(tmp_path):
    """When the live repo's count matches the manifest, no FAIL is produced."""
    repo_dir = tmp_path / "mcp-factory"
    _write_fake_runner(repo_dir, passed_count=199)
    entries = {"mcp-factory": _fake_entry(repo_dir, value=199)}

    results = cpn.live_verify_manifest(entries)

    fails = [r for r in results if r.status == "FAIL"]
    oks = [r for r in results if r.status == "OK"]
    assert fails == []
    assert len(oks) == 1
    assert oks[0].live_value == 199


def test_live_check_missing_repo_warns_not_fails(tmp_path):
    """A source_repo that doesn't exist on this machine (e.g. CI without every
    sibling repo checked out) must WARN, never FAIL -- it must not block an
    unrelated commit just because one repo isn't present locally."""
    missing_repo = tmp_path / "does-not-exist"
    entries = {
        "mcp-factory": cpn.ManifestEntry(
            key="mcp-factory", value=199,
            source_cmd=f"{sys.executable} fake_runner.py",
            source_repo=str(missing_repo),
        )
    }

    results = cpn.live_verify_manifest(entries)

    assert len(results) == 1
    assert results[0].status == "WARN"
    fails = [r for r in results if r.status == "FAIL"]
    assert fails == []


def test_live_check_missing_venv_warns_not_fails(tmp_path):
    """A repo that exists but whose pinned venv interpreter is missing
    (e.g. ".venv/Scripts/python.exe" not present) must WARN, not FAIL --
    a repo without its venv set up locally shouldn't block a site commit."""
    repo_dir = tmp_path / "mcp-factory"
    repo_dir.mkdir()
    entries = {
        "mcp-factory": cpn.ManifestEntry(
            key="mcp-factory", value=199,
            source_cmd=".venv/Scripts/python.exe -m pytest -q",
            source_repo=str(repo_dir),
        )
    }

    results = cpn.live_verify_manifest(entries)

    assert len(results) == 1
    assert results[0].status == "WARN"
    assert "venv" in results[0].message.lower() or "interpreter" in results[0].message.lower()


def test_live_check_timeout_warns_not_fails(tmp_path):
    """A source_cmd that hangs past the timeout must WARN, not FAIL or hang
    the commit forever."""
    repo_dir = tmp_path / "mcp-factory"
    _write_fake_runner(repo_dir, passed_count=199, extra_py="import time; time.sleep(5)")
    entries = {"mcp-factory": _fake_entry(repo_dir, value=199)}

    results = cpn.live_verify_manifest(entries, timeout=1)

    assert len(results) == 1
    assert results[0].status == "WARN"
    assert "timed out" in results[0].message.lower()
    fails = [r for r in results if r.status == "FAIL"]
    assert fails == []


def test_live_check_strips_inherited_git_env_vars(tmp_path, monkeypatch):
    """Real 2026-07-21 incident: when this script runs as an actual git
    pre-commit hook, git sets GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE for its
    OWN hook subprocess -- those leaked into the live-check's subprocess.run
    via plain env inheritance. Since the live-check spawns a DIFFERENT
    repo's test suite, and that suite may do its own git operations
    (mcp-factory's test_workflow_runner.py calls `git ls-files`), the
    inherited vars pointed those git calls at the WRONG repo -- 20 tests
    failed as a result (215 -> 195 passed), silently, and only when invoked
    through a real `git commit` (never reproduced standalone). This test
    simulates that exact environment and proves the live-check reports the
    clean count regardless."""
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "unrelated-other-repo" / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "unrelated-other-repo"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "unrelated-other-repo" / ".git" / "index"))

    repo_dir = tmp_path / "mcp-factory"
    # The fake runner reports a DIFFERENT (corrupted) count if it can see
    # GIT_DIR in its own environment -- mirroring the real bug's shape,
    # where an inherited git-context var changes the subprocess's behavior.
    _write_fake_runner(
        repo_dir, passed_count=215,
        extra_py=(
            "import os\n"
            "if os.environ.get('GIT_DIR'):\n"
            "    print('195 passed in 0.01s')\n"
            "    raise SystemExit(0)\n"
        ),
    )
    entries = {"mcp-factory": _fake_entry(repo_dir, value=215)}

    results = cpn.live_verify_manifest(entries)

    fails = [r for r in results if r.status == "FAIL"]
    assert fails == [], (
        f"live-check should report the clean 215 count regardless of the "
        f"caller's own GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE -- got {results!r}")
    oks = [r for r in results if r.status == "OK"]
    assert len(oks) == 1 and oks[0].live_value == 215


def test_live_check_no_source_repo_is_skipped_silently(tmp_path):
    """Entries with no source_repo (schema allows it -- only value/source_cmd
    are required) simply can't be live-checked and produce no result at all,
    not even a WARN -- this is the normal/expected shape for such entries."""
    entries = {"mcp-factory": cpn.ManifestEntry(key="mcp-factory", value=199, source_cmd="pytest -q", source_repo=None)}
    results = cpn.live_verify_manifest(entries)
    assert results == []


def test_run_end_to_end_live_check_fails_even_when_citations_agree(tmp_path, monkeypatch):
    """Integration: three-way agreement. Site citations matching the manifest
    is no longer sufficient -- if the manifest itself has drifted from the
    live repo, run() must still exit 2, with the live-check FAIL printed."""
    monkeypatch.delenv(cpn.SKIP_LIVE_CHECK_ENV_VAR, raising=False)
    repo_dir = tmp_path / "mcp-factory"
    _write_fake_runner(repo_dir, passed_count=207)

    manifest_toml = tmp_path / "proof-manifest.toml"
    manifest_toml.write_text(
        '["mcp-factory"]\n'
        "value = 199\n"
        f'source_cmd = "{Path(sys.executable).as_posix()} fake_runner.py"\n'
        f'source_repo = "{repo_dir.as_posix()}"\n',
        encoding="utf-8",
    )
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    # Site citation agrees with the (stale) manifest -- the old citation-only
    # gate would have passed this commit.
    write(site_dir, "index.html", "<p>mcp-factory: 199 passing tests</p>\n")

    exit_code = cpn.run(root=site_dir, manifest_path=manifest_toml, target_patterns=["*.html"])

    assert exit_code == 2, "manifest-vs-live drift must fail the gate even when site citations match the manifest"


def test_run_respects_skip_live_check_env_var(tmp_path, monkeypatch):
    """Opt-out escape hatch: PROOF_NUMBERS_SKIP_LIVE_CHECK=1 skips the live
    pass entirely (citation-vs-manifest check still runs)."""
    monkeypatch.setenv(cpn.SKIP_LIVE_CHECK_ENV_VAR, "1")
    repo_dir = tmp_path / "mcp-factory"
    _write_fake_runner(repo_dir, passed_count=207)

    manifest_toml = tmp_path / "proof-manifest.toml"
    manifest_toml.write_text(
        '["mcp-factory"]\n'
        "value = 199\n"
        f'source_cmd = "{Path(sys.executable).as_posix()} fake_runner.py"\n'
        f'source_repo = "{repo_dir.as_posix()}"\n',
        encoding="utf-8",
    )
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    write(site_dir, "index.html", "<p>mcp-factory: 199 passing tests</p>\n")

    exit_code = cpn.run(root=site_dir, manifest_path=manifest_toml, target_patterns=["*.html"])

    assert exit_code == 0, "with the live check skipped, citation-vs-manifest agreement alone should pass"


def _bash_path() -> str:
    path = shutil.which("bash")
    if path is None:
        pytest.skip("bash not found on PATH -- cannot exercise the shell hook end-to-end")
    return path


def _build_temp_hook_repo(tmp_path: Path, manifest_toml_text: str, index_html_text: str) -> Path:
    """Build a minimal git repo with the REAL .githooks/pre-commit and the
    REAL scripts/check_proof_numbers.py wired up, so the shell-script-level
    fixes (findings 4 and 5) are exercised end-to-end rather than only
    unit-tested at the Python level. Never touches the real repo's checkout."""
    repo = tmp_path / "hookrepo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)

    (repo / "scripts").mkdir()
    shutil.copy2(REPO_ROOT / "scripts" / "check_proof_numbers.py", repo / "scripts" / "check_proof_numbers.py")
    (repo / ".githooks").mkdir()
    shutil.copy2(REPO_ROOT / ".githooks" / "pre-commit", repo / ".githooks" / "pre-commit")

    (repo / "proof-manifest.toml").write_text(manifest_toml_text, encoding="utf-8", newline="\n")
    (repo / "index.html").write_text(index_html_text, encoding="utf-8", newline="\n")
    return repo


def test_hook_file_is_committed_executable():
    """Reviewer finding 4 repro: .githooks/pre-commit was checked in
    non-executable (mode 100644). On Linux/macOS, git silently skips a
    non-executable hook file -- core.hooksPath would be configured but the
    gate would never actually run. The exec bit must be committed (100755)."""
    result = subprocess.run(
        ["git", "ls-files", "-s", ".githooks/pre-commit"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    mode = result.stdout.split()[0]
    assert mode == "100755", f"expected the hook committed executable (100755), got: {result.stdout!r}"


def test_hook_blocked_message_survives_set_e(tmp_path):
    """Reviewer finding 5 repro: `set -e` previously aborted the hook's shell
    on the checker's non-zero exit BEFORE the STATUS=$?/guidance-message
    block ran (a bare failing command is not exempt from set -e; only a
    command used as an `if`/`&&`/`||` operand is), so a blocked commit
    printed a bare tool dump instead of the 'pre-commit: BLOCKED ...' fix
    guidance. Runs the REAL .githooks/pre-commit end-to-end against a stale
    fixture and asserts both: the commit is still blocked (non-zero exit)
    AND the guidance message actually printed."""
    bash = _bash_path()
    manifest_toml_text = '["mcp-factory"]\nvalue = 187\nsource_cmd = "pytest -q"\n'
    stale_index = "<p>mcp-factory: 179 passing tests</p>\n"
    repo = _build_temp_hook_repo(tmp_path, manifest_toml_text, stale_index)

    result = subprocess.run([bash, ".githooks/pre-commit"], cwd=repo, capture_output=True, text=True)

    assert result.returncode != 0, f"stale commit must still be blocked: {result.stdout}\n{result.stderr}"
    assert "BLOCKED" in result.stdout, (
        f"guidance message must survive set -e, not be swallowed by it: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_hook_allows_clean_commit_with_no_blocked_message(tmp_path):
    """Sanity companion to the set-e regression: the same real hook, run
    against a fixture where the proof number is correct, exits 0 and never
    prints the BLOCKED guidance."""
    bash = _bash_path()
    manifest_toml_text = '["mcp-factory"]\nvalue = 187\nsource_cmd = "pytest -q"\n'
    clean_index = "<p>mcp-factory: 187 passing tests</p>\n"
    repo = _build_temp_hook_repo(tmp_path, manifest_toml_text, clean_index)

    result = subprocess.run([bash, ".githooks/pre-commit"], cwd=repo, capture_output=True, text=True)

    assert result.returncode == 0, f"clean commit must pass: {result.stdout}\n{result.stderr}"
    assert "BLOCKED" not in result.stdout


def test_live_check_source_env_reaches_subprocess(tmp_path):
    """A manifest entry may carry a source_env table; those variables must be
    set in the source_cmd subprocess. Real use: mcp-factory's live count on
    the fleet machine differs from the clean-checkout count because
    test_smoke_hub discovers the live bot fleet -- pointing
    MCP_FACTORY_SMOKE_ROOTS at an empty fixture dir reproduces the
    clean-checkout number (222) that public CI gates on."""
    repo_dir = tmp_path / "mcp-factory"
    _write_fake_runner(
        repo_dir,
        passed_count=224,
        extra_py=(
            "import os\n"
            "if os.environ.get('FAKE_SMOKE_ROOTS'):\n"
            "    print('222 passed in 0.01s')\n"
            "    raise SystemExit(0)\n"
        ),
    )
    entry = cpn.ManifestEntry(
        key="mcp-factory",
        value=222,
        source_cmd=f"{sys.executable} fake_runner.py",
        source_repo=str(repo_dir),
        source_env={"FAKE_SMOKE_ROOTS": "anything"},
    )

    results = cpn.live_verify_manifest({"mcp-factory": entry})

    fails = [r for r in results if r.status == "FAIL"]
    oks = [r for r in results if r.status == "OK"]
    assert fails == []
    assert len(oks) == 1
    assert oks[0].live_value == 222


def test_live_check_without_source_env_unchanged(tmp_path):
    """Entries with no source_env behave exactly as before (env untouched)."""
    repo_dir = tmp_path / "mcp-factory"
    _write_fake_runner(repo_dir, passed_count=199)
    entries = {"mcp-factory": _fake_entry(repo_dir, value=199)}
    results = cpn.live_verify_manifest(entries)
    assert [r.status for r in results] == ["OK"]


def test_manifest_source_env_loads_and_validates(tmp_path):
    """source_env loads as a str->str table; a non-string value fails the
    whole load loudly (same philosophy as the other schema checks)."""
    good = tmp_path / "good.toml"
    good.write_text(
        '["mcp-factory"]\n'
        'value = 222\n'
        'source_cmd = "python -m pytest -q"\n'
        'source_env = { MCP_FACTORY_SMOKE_ROOTS = "C:/x/empty" }\n',
        encoding="utf-8",
    )
    entries = cpn.load_manifest_entries(good)
    assert entries["mcp-factory"].source_env == {
        "MCP_FACTORY_SMOKE_ROOTS": "C:/x/empty"}

    bad = tmp_path / "bad.toml"
    bad.write_text(
        '["mcp-factory"]\n'
        'value = 222\n'
        'source_cmd = "python -m pytest -q"\n'
        'source_env = { MCP_FACTORY_SMOKE_ROOTS = 7 }\n',
        encoding="utf-8",
    )
    try:
        cpn.load_manifest_entries(bad)
        raise AssertionError("expected ManifestValidationError")
    except cpn.ManifestValidationError as exc:
        assert "source_env" in str(exc)


# --- junitxml live-check parsing (2026-07-23 lane: 7 recurring LIVE-CHECK
# WARNs from repos whose pytest config suppresses the plain "-q" summary
# line under piped/non-tty capture -- github-mcp, desktop-mcp, rag-mcp,
# bus-mcp, discord-mcp, rails-mcp, vllm-ops-mcp, live-verified 2026-07-23:
# dots + "[100%]" only, zero "passed" text anywhere in stdout/stderr) ---

def test_parse_junit_counts_testsuites_wrapper(tmp_path):
    """Current pytest wraps a single <testsuite> in a <testsuites> root
    (verified live against rag-mcp 2026-07-23)."""
    xml_path = tmp_path / "junit.xml"
    xml_path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites name="pytest tests">'
        '<testsuite name="pytest" errors="0" failures="0" skipped="2" tests="62">'
        '</testsuite></testsuites>',
        encoding="utf-8",
    )
    assert cpn._parse_junit_counts(xml_path) == 60


def test_parse_junit_counts_bare_testsuite_root(tmp_path):
    """Older pytest / other runners may emit a bare <testsuite> root with no
    wrapping <testsuites> -- must be handled too."""
    xml_path = tmp_path / "junit.xml"
    xml_path.write_text(
        '<testsuite name="pytest" errors="1" failures="1" skipped="0" tests="10">'
        '</testsuite>',
        encoding="utf-8",
    )
    assert cpn._parse_junit_counts(xml_path) == 8


def test_parse_junit_counts_missing_file_returns_none(tmp_path):
    assert cpn._parse_junit_counts(tmp_path / "does-not-exist.xml") is None


def test_parse_junit_counts_malformed_xml_returns_none(tmp_path):
    xml_path = tmp_path / "junit.xml"
    xml_path.write_text("not xml at all <<<", encoding="utf-8")
    assert cpn._parse_junit_counts(xml_path) is None


def test_parse_dot_count_single_line():
    output = "." * 60 + "             [100%]\n"
    assert cpn._parse_dot_count(output) == 60


def test_parse_dot_count_multi_line_wrap():
    """github-mcp's real captured shape (verified live 2026-07-23): a
    percentage-wrapped line followed by a final [100%] line."""
    output = (
        "." * 40 + "s" + "." * 33 + " [ 73%]\n"
        + "." * 26 + "                                                          [100%]\n"
    )
    assert cpn._parse_dot_count(output) == 40 + 33 + 26


def test_parse_dot_count_ignores_warnings_summary_prose():
    """Prose in a warnings-summary section (which also contains periods)
    must never be mistaken for progress dots -- only lines that are
    entirely outcome characters followed by a "[ NN%]" marker count."""
    output = (
        "." * 10 + "          [100%]\n"
        "=== warnings summary ===\n"
        "test_foo.py::test_bar uses a deprecated thing. Please migrate.\n"
    )
    assert cpn._parse_dot_count(output) == 10


def test_parse_dot_count_no_progress_lines_returns_none():
    output = "collected 0 items\n\nno tests ran in 0.00s\n"
    assert cpn._parse_dot_count(output) is None


def test_prepare_junit_argv_appends_when_absent(tmp_path):
    """No existing --junitxml convention -- one is appended pointing into
    the given scratch dir."""
    argv = ["python", "-m", "pytest", "-q"]
    new_argv, junit_path = cpn._prepare_junit_argv(argv, tmp_path)
    assert new_argv[:4] == argv
    assert new_argv[4].startswith("--junitxml=")
    assert junit_path.parent == tmp_path


def test_prepare_junit_argv_substitutes_scratch_placeholder(tmp_path):
    """The bus-mcp manifest convention already embeds
    --junitxml=<scratch>/bus.xml -- <scratch> must be substituted with a
    real temp path, not passed through literally."""
    argv = ["python", "-m", "pytest", "-q", "--junitxml=<scratch>/bus.xml"]
    new_argv, junit_path = cpn._prepare_junit_argv(argv, tmp_path)
    assert "<scratch>" not in new_argv[-1]
    assert junit_path == tmp_path / "bus.xml"


def test_prepare_junit_argv_respects_existing_concrete_path(tmp_path):
    """A source_cmd that already names a concrete (non-placeholder)
    --junitxml path is left untouched."""
    concrete = tmp_path / "already-set.xml"
    argv = ["python", "-m", "pytest", "-q", f"--junitxml={concrete}"]
    new_argv, junit_path = cpn._prepare_junit_argv(argv, tmp_path)
    assert new_argv == argv
    assert junit_path == concrete


def test_live_check_uses_junitxml_when_summary_suppressed(tmp_path):
    """Core fix: a fake runner that suppresses its summary line entirely
    (dots + [100%] only, no 'passed' text anywhere) but DOES honor an
    appended --junitxml flag must still be live-verified correctly via the
    junit report -- this is the github-mcp/desktop-mcp/rag-mcp/bus-mcp/
    discord-mcp/rails-mcp/vllm-ops-mcp class of repo that previously fell
    straight to an unresolved WARN and silently skipped live verification."""
    repo_dir = tmp_path / "github-mcp"
    _write_junit_capable_fake_runner(repo_dir, tests=88, skipped=2)
    entry = cpn.ManifestEntry(
        key="github-mcp", value=86,
        source_cmd=f"{sys.executable} fake_runner.py -q",
        source_repo=str(repo_dir),
    )
    results = cpn.live_verify_manifest({"github-mcp": entry})
    assert len(results) == 1
    assert results[0].status == "OK"
    assert results[0].live_value == 86  # 88 tests - 2 skipped = 86 passed


def test_live_check_junitxml_mismatch_fails(tmp_path):
    repo_dir = tmp_path / "github-mcp"
    _write_junit_capable_fake_runner(repo_dir, tests=90, skipped=2)
    entry = cpn.ManifestEntry(
        key="github-mcp", value=86,
        source_cmd=f"{sys.executable} fake_runner.py -q",
        source_repo=str(repo_dir),
    )
    results = cpn.live_verify_manifest({"github-mcp": entry})
    assert results[0].status == "FAIL"
    assert results[0].live_value == 88
    assert results[0].expected == 86


def test_live_check_respects_scratch_placeholder_convention(tmp_path):
    """The bus-mcp manifest entry's source_cmd already embeds a
    --junitxml=<scratch>/bus.xml convention; the live-check must substitute
    <scratch> with a real temp path rather than trying to write literally
    into a directory named '<scratch>'."""
    repo_dir = tmp_path / "bus-mcp"
    _write_junit_capable_fake_runner(repo_dir, tests=63, skipped=1)
    entry = cpn.ManifestEntry(
        key="bus-mcp", value=62,
        source_cmd=f"{sys.executable} fake_runner.py -q --junitxml=<scratch>/bus.xml",
        source_repo=str(repo_dir),
    )
    results = cpn.live_verify_manifest({"bus-mcp": entry})
    assert results[0].status == "OK"
    assert results[0].live_value == 62


def test_live_check_falls_back_to_dot_count_when_no_junit_and_no_summary(tmp_path):
    """A source_cmd/tool that neither honors --junitxml nor prints a
    parseable summary line falls back to counting progress-dot characters
    -- the least-precise but still-better-than-nothing last resort."""
    repo_dir = tmp_path / "some-tool"
    _write_dots_only_fake_runner(repo_dir, passed_count=45)
    entry = cpn.ManifestEntry(
        key="mcp-factory", value=45,
        source_cmd=f"{sys.executable} fake_runner.py",
        source_repo=str(repo_dir),
    )
    results = cpn.live_verify_manifest({"mcp-factory": entry})
    assert results[0].status == "OK"
    assert results[0].live_value == 45


def test_live_check_junitxml_preferred_over_summary_line_when_both_present(tmp_path):
    """If a runner emits BOTH a junitxml report and a plain summary line,
    junitxml wins (it's the structurally reliable source) -- the fake
    summary line here deliberately lies (999) to prove precedence."""
    repo_dir = tmp_path / "github-mcp"
    _write_junit_capable_fake_runner(
        repo_dir, tests=88, skipped=2, fake_summary_passed=999,
    )
    entry = cpn.ManifestEntry(
        key="github-mcp", value=86,
        source_cmd=f"{sys.executable} fake_runner.py",
        source_repo=str(repo_dir),
    )
    results = cpn.live_verify_manifest({"github-mcp": entry})
    assert results[0].status == "OK"
    assert results[0].live_value == 86
