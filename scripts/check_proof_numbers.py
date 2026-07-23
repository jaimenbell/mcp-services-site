#!/usr/bin/env python3
"""check_proof_numbers.py -- commit-time proof-number gate.

Problem this guards against: a test-count / proof-number ("179 passing tests")
gets cited on the public site, the upstream repo's suite grows or shrinks, and
the site quietly drifts out of sync with reality (the 179-vs-187 mcp-factory
class of bug). This script scans committed site content for proof-number
citations and fails the commit if any of them contradicts proof-manifest.toml
-- the manifest whose values are only ever seeded by actually running the
upstream suite (see proof-manifest.toml's own header + this repo's lane
report for the verbatim pytest tail lines used to seed it).

MATCHING / ASSOCIATION RULES (read this before changing the regexes below)
---------------------------------------------------------------------------
1. A line is only scanned for candidate numbers if it contains one of the
   TRIGGER words: "test", "tests", "passing", "passed" (case-insensitive).
   This is the primary false-positive guard: prices, years, IDs, tool counts
   ("18 tools"), day counts, etc. never appear next to those words and are
   never touched.

2. Within a trigger line, LABEL_PATTERNS finds numbers that are labelled as
   a test count, in any of these realistic copy-editing shapes:
     a. PATTERN_LABELLED: "<N> tests", "<N> passing tests", "<N> passed",
        "<N> passing", or the "<N> + <M> tests" fleet-stat shape -- number
        directly adjacent to the label.
     b. PATTERN_LABELLED_GAP: "<N> <word> tests" -- one intervening word
        between the number and the label, e.g. "200 unit tests".
     c. PATTERN_HYPHENATED: "<N>-test(s)" -- hyphenated, e.g. "200-test
        suite".
     d. PATTERN_LABEL_BEFORE: "tests: <N>", "tests passing: <N>", "passing:
        <N>" -- label before the number, colon-separated.
   Each pattern requires the label to be genuinely adjacent (not just present
   anywhere on the line) -- this is what lets "121 passing tests" match while
   "18 tools . 121 passing tests" still only flags the 121, never the 18. A
   candidate match is discarded if its span overlaps one already accepted by
   an earlier pattern, so one citation is never counted twice.

   PATTERN_LABELLED and PATTERN_LABELLED_GAP additionally refuse to match
   when "tests"/"passing"/"passed" is immediately followed by a complement
   word (whether/if/that/how/what/why/this/these/those/the/a/an) -- this is
   the guard against "tests" used as a VERB, e.g. scoreboard.html's "Wave 7
   tests whether this collapses into news_veto..." ("[Wave 7] tests
   [whether ...]" is a sentence, not a "7 tests" proof-number citation).

3. PATTERN_ROSTER additionally catches the "Test counts (179 mcp-factory, 50
   rag-mcp, 186 options-bot)" idiom: a line whose text contains "test count"
   followed by a parenthesised comma list of "<N> <repo-slug>" pairs. This is
   a narrow, explicitly-named idiom (not a generic number-near-word rule) so
   it does not widen the false-positive surface from rule 1.

4. ASSOCIATION -- once a candidate number is found, it must be tied to a repo
   before it can be judged against the manifest:
     a. PATTERN_ROSTER pairs already carry their repo slug directly.
     b. Otherwise, if a manifest repo key (e.g. "mcp-factory") appears as a
        substring anywhere on the same line, associate with it. If more than
        one manifest key appears on the line, associate each number with the
        nearest one by character distance.
     c. Otherwise, if the file's own basename (minus extension) matches a
        manifest key (e.g. case-studies/mcp-factory.html), associate with it.
     d. Otherwise, search up to WINDOW lines above and below in the same file
        for the nearest occurrence of a manifest key (covers index.html's
        proof-card blocks, where the repo name sits in a neighbouring <a
        href> or <h3> line, not the same line as the number).
     e. Otherwise: UNRESOLVED.

5. VERDICT:
     - Associated with a manifest key, number != manifest value  -> FAIL
     - Associated with a manifest key, number == manifest value  -> pass (silent)
     - Associated with a non-manifest keyword (e.g. "options-bot",
       "fleet-reliability-day") or UNRESOLVED                    -> WARN
   FAIL occurrences make the process exit 2. WARN occurrences are printed but
   never affect the exit code.

Stdlib only. ASCII-only. Works under any of python3 / python / py.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "proof-manifest.toml"

# Live-check knobs (see LiveCheckResult / live_verify_manifest below).
LIVE_CHECK_TIMEOUT_SECONDS = 90
SKIP_LIVE_CHECK_ENV_VAR = "PROOF_NUMBERS_SKIP_LIVE_CHECK"

# Files scanned by default when this script is run with no arguments (the
# pre-commit hook uses this list). Callers (tests) may pass explicit paths
# instead.
DEFAULT_TARGET_GLOBS = [
    "index.html",
    "GO-LIVE.md",
    "README.md",
    "case-studies/*.html",
    "case-studies/*.md",
    "articles/*.html",
    "scoreboard.html",
    "404.html",
]

TRIGGER_RE = re.compile(r"\b(?:tests?|passing|passed)\b", re.IGNORECASE)

NUM = r"(\d{1,3}(?:,\d{3})+|\d+)"

# "<N> [+ <M>] <label>" -- number(s) immediately followed by a labelling word.
# Guard against "tests" used as a VERB rather than a test-count noun, e.g.
# "Wave 7 tests whether this collapses..." (scoreboard.html) -- "tests" here
# is present-tense "[Wave 7] tests [whether ...]", not "7 tests" the count.
# As a noun/participle, "tests"/"passing"/"passed" is followed by a phrase
# boundary (punctuation, a closing tag, "and", "cover", "exercise", etc);
# as a verb it takes a direct complement introduced by one of these words.
_NOT_VERB_COMPLEMENT = r"(?!\s+(?:whether|if|that|how|what|why|this|these|those|the|a|an)\b)"

PATTERN_LABELLED = re.compile(
    rf"{NUM}(?:\s*\+\s*{NUM})?\s+(?:passing\s+tests|passed\s+tests|passing|passed|tests?)\b{_NOT_VERB_COMPLEMENT}",
    re.IGNORECASE,
)

# "<N> <word> <label>" -- number-before-label with ONE intervening word, e.g.
# "mcp-factory ships with 200 unit tests". The negative lookahead keeps this
# from double-matching plain "<N> passing tests" (already caught by
# PATTERN_LABELLED above) by refusing to treat a label word itself as the
# "intervening word".
PATTERN_LABELLED_GAP = re.compile(
    rf"{NUM}\s+(?!(?:passing|passed|tests?)\b)[a-zA-Z]+\s+"
    rf"(?:passing\s+tests|passed\s+tests|passing|passed|tests?)\b{_NOT_VERB_COMPLEMENT}",
    re.IGNORECASE,
)

# "<N>-test[s]" -- hyphenated number-before-label, e.g. "a 200-test suite".
PATTERN_HYPHENATED = re.compile(rf"{NUM}-tests?\b", re.IGNORECASE)

# Label-before-number, e.g. "tests: 200", "tests passing: 200", "passing: 200".
# Bounded intervening word (max 20 chars) keeps this from wandering across
# unrelated colons elsewhere on a long line.
PATTERN_LABEL_BEFORE = re.compile(
    rf"\b(?:tests?|passing|passed)\b(?:\s+\w{{1,20}})?\s*:\s*{NUM}\b",
    re.IGNORECASE,
)

# Every labelled-number matcher, tried in order; a candidate match is skipped
# if it overlaps a span already accepted by an earlier pattern in the list,
# so a single citation is never counted twice (see rule 2 in the module
# docstring below for the realistic copy-editing variants each one covers).
LABEL_PATTERNS = [PATTERN_LABELLED, PATTERN_LABELLED_GAP, PATTERN_HYPHENATED, PATTERN_LABEL_BEFORE]

# "Test count(s) (<N> repo-slug, <M> repo-slug, ...)" idiom.
ROSTER_LINE_RE = re.compile(r"test\s+counts?", re.IGNORECASE)
ROSTER_PAIR_RE = re.compile(rf"{NUM}\s+([a-zA-Z][a-zA-Z0-9_-]{{1,40}})")

WINDOW = 10  # lines to search above/below for association fallback (d)

# Rule 4f (by-value fallback): when a labelled proof-number has no nearby
# repo label at all (steps a-d all miss), associate it by VALUE instead of
# leaving it as a silent, unchecked WARN:
#   - if the number equals EXACTLY ONE manifest entry's value, treat it as
#     that repo's citation and verify it normally (this is what makes
#     index.html's decorative "187 passing / 74 tests / 121 tests" span and
#     the og:/twitter:description meta tags -- all of which sit far outside
#     the 10-line WINDOW of any proof-card's repo label -- actually get
#     checked instead of silently WARNing forever);
#   - if it matches NO manifest value and isn't in KNOWN_NONCANONICAL_NUMBERS
#     below, it is presumed a drifted/uncanonical proof-number citation and
#     FAILs (rather than WARNing) -- an orphaned number in test-count context
#     with no explanation is exactly the kind of silent drift this gate
#     exists to catch;
#   - if it matches MORE THAN ONE manifest value (a value collision) it is
#     ambiguous -- we cannot know which repo it was meant to cite -- so it is
#     treated the same as "matches no manifest value" for verdict purposes:
#     FAIL unless it is in the known-noncanonical allowlist below (never
#     silently assumed correct just because it happens to match something).
#
# KNOWN_NONCANONICAL_NUMBERS is a small, deliberately curated allowlist of
# numbers that legitimately appear in test-count-shaped prose but do NOT
# correspond to any single manifest-tracked repo suite, so by-value
# association can never resolve them and they must not be escalated to FAIL:
#   - 186: options-bot's own test count. options-bot is a separate project
#     outside this manifest's scope (not one of the MCP servers this site
#     sells) -- see case-studies/honest-harness.html and GO-LIVE.md. Its
#     count is cited for narrative honesty but is not live-verified by this
#     repo's tooling, so it has no proof-manifest.toml entry to check against.
#   - 2806, 283: case-studies/fleet-reliability-day.html's "N + M tests"
#     composite -- an aggregate across ~30 fleet lanes, not any single repo's
#     suite count, so it has no single manifest entry either.
#   - 1002: day-trader's full-suite test count, cited in
#     case-studies/orphan-position-recovery.html. day-trader is a live trading
#     repo, deliberately kept off this manifest and out of the public repo set
#     (see github-profile.md's "do NOT rush to publish" list) -- its count is
#     quotable for narrative honesty (live-verified in its own .venv,
#     2026-07-21: 1002 passed) but not tracked here since the repo itself is
#     never linked from the site.
#   - 17: the number of new tests shipped with day-trader's orphan-lifecycle
#     hardening (same case study) -- a delta within the untracked 1002-test
#     day-trader suite above, not a separate repo's total.
# When adding a new named-but-untracked proof-number callout to the site,
# add its value(s) here (with a comment explaining why it's untracked) or it
# will start FAILing the commit gate as a suspicious orphaned number.
KNOWN_NONCANONICAL_NUMBERS = {186, 2806, 283, 1002, 17}


class Finding:
    def __init__(self, file: Path, line_no: int, line_text: str, number: int,
                 repo_key: str | None, verdict: str, expected: int | None = None):
        self.file = file
        self.line_no = line_no
        self.line_text = line_text
        self.number = number
        self.repo_key = repo_key
        self.verdict = verdict  # "FAIL" | "WARN"
        self.expected = expected

    def format(self) -> str:
        rel = self.file
        # ASCII-only output: this script's hard rail applies to what it prints,
        # not just its own source, since the hook that invokes it must run
        # safely under any shell/codepage. Non-ASCII bytes in scanned HTML/MD
        # (curly quotes, em-dashes, checkmarks) are replaced, never crashed on.
        snippet = self.line_text.strip().encode("ascii", errors="replace").decode("ascii")
        if self.verdict == "FAIL":
            if self.repo_key is None and self.expected is None:
                return (
                    f"FAIL {rel}:{self.line_no}: found {self.number} -- no manifest"
                    f" entry has this value and it is not a documented"
                    f" known-non-canonical exception; suspicious/uncanonical"
                    f" proof-number citation -- {snippet}"
                )
            return (
                f"FAIL {rel}:{self.line_no}: found {self.number}"
                f" (repo={self.repo_key}), expected {self.expected}"
                f" per proof-manifest.toml -- {snippet}"
            )
        repo_part = f" (repo={self.repo_key})" if self.repo_key else " (no repo association)"
        return f"WARN {rel}:{self.line_no}: found {self.number}{repo_part} -- not in manifest -- {snippet}"


PASSED_RE = re.compile(r"(\d+)\s+passed")

# Junitxml live-check support (2026-07-23 fix): 7 repos (github-mcp,
# desktop-mcp, rag-mcp, bus-mcp, discord-mcp, rails-mcp, vllm-ops-mcp)
# suppress pytest's plain "-q" summary line entirely under piped/non-tty
# capture -- verified live 2026-07-23: output is dots + "[100%]" only, zero
# "passed" text anywhere in stdout/stderr. Those entries previously fell
# straight through PASSED_RE to an unresolved "could not parse" WARN and
# silently skipped live verification -- the exact class this checker exists
# to prevent. The fix: request a junitxml report from the live-checked
# command and parse tests/failures/errors/skipped from it, falling back to
# the summary-line parse, then a dot-count parse, in that order of
# reliability.
JUNITXML_TOKEN_RE = re.compile(r"^--junitxml=(.+)$")
SCRATCH_TOKEN = "<scratch>"

# Last-resort fallback when neither junitxml nor a "N passed" summary line
# is available: count '.' (passed) outcome characters from pytest -q's
# per-test progress-dot lines. Only lines that are ENTIRELY outcome
# characters ('.', 'F', 'E', 's', 'x', 'X') followed by a "[ NN%]" progress
# marker are counted -- this keeps unrelated prose (e.g. a warnings-summary
# section, which also contains periods) from ever being mistaken for
# progress dots.
DOT_LINE_RE = re.compile(r"^([.FEsxX]+)\s*\[\s*\d+%\]\s*$")


def _prepare_junit_argv(argv: list[str], scratch_dir: Path) -> tuple[list[str], Path]:
    """Ensure `argv` will produce a junitxml report, returning the
    (possibly modified) argv and the path the report will be written to.

    Three cases, in priority order:
      1. argv already names a --junitxml=<scratch>/... path (the bus-mcp
         manifest convention) -- substitute the <scratch> placeholder with
         `scratch_dir` and use that as the report path.
      2. argv already names a concrete (non-placeholder) --junitxml path --
         leave it untouched and use that path as-is.
      3. No --junitxml token at all -- append one pointing into
         `scratch_dir`, so every live-checked command gets a junit report
         regardless of whether the manifest entry asked for one.
    """
    new_argv = list(argv)
    for i, tok in enumerate(new_argv):
        m = JUNITXML_TOKEN_RE.match(tok)
        if not m:
            continue
        raw_path = m.group(1)
        if SCRATCH_TOKEN in raw_path:
            raw_path = raw_path.replace(SCRATCH_TOKEN, str(scratch_dir))
            new_argv[i] = f"--junitxml={raw_path}"
        return new_argv, Path(raw_path)
    junit_path = scratch_dir / "live_check_junit.xml"
    new_argv.append(f"--junitxml={junit_path}")
    return new_argv, junit_path


def _parse_junit_counts(junit_path: Path) -> int | None:
    """Parse a pytest junitxml report and return the passed-test count
    (tests - failures - errors - skipped), or None if the file doesn't
    exist, isn't well-formed XML, or is missing the expected attributes.
    Handles both a bare <testsuite> root and a <testsuites> root wrapping
    one or more <testsuite> children (current pytest's shape, verified
    live against rag-mcp 2026-07-23)."""
    if not junit_path.exists():
        return None
    try:
        root = ET.parse(junit_path).getroot()
    except ET.ParseError:
        return None
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        return None
    total_tests = total_failures = total_errors = total_skipped = 0
    for suite in suites:
        try:
            total_tests += int(suite.get("tests", 0))
            total_failures += int(suite.get("failures", 0))
            total_errors += int(suite.get("errors", 0))
            total_skipped += int(suite.get("skipped", 0))
        except (TypeError, ValueError):
            return None
    return total_tests - total_failures - total_errors - total_skipped


def _parse_dot_count(output: str) -> int | None:
    """Last-resort fallback: count '.' (passed) outcome characters from
    pytest -q's per-test progress-dot lines, when neither a junitxml report
    nor a parseable "N passed" summary line is available. Windows can
    mangle -q's progress output with bare \\r (carriage-return) overwrites
    when a real console is attached (a known trap -- see the
    proof-numbers-drift-log memory) -- strip stray \\r characters outright
    (never translate them into fabricated newlines, which would double- or
    under-count a cumulative-overwrite frame) before line-splitting on the
    real \\n boundaries actually used by piped/non-tty capture (verified
    live 2026-07-23: no \\r appears at all when captured via
    subprocess.run(..., capture_output=True), only plain \\n)."""
    cleaned = output.replace("\r", "")
    total = None
    for line in cleaned.splitlines():
        m = DOT_LINE_RE.match(line.strip())
        if not m:
            continue
        if total is None:
            total = 0
        total += m.group(1).count(".")
    return total


class LiveCheckResult:
    """Outcome of live-verifying one manifest entry against its source_repo.

    status is one of:
      "FAIL" -- repo + interpreter were reachable, source_cmd ran and produced
                a parseable "N passed" count, and it DISAGREES with the
                manifest's value. This is the case the whole live-check exists
                to catch: the manifest itself has gone stale relative to the
                repo it claims to describe.
      "WARN" -- live-checking wasn't possible (no source_repo on this machine,
                venv/interpreter missing, source_cmd timed out or errored, or
                its output couldn't be parsed). Never escalated to FAIL --
                CI or a teammate's clone won't have every sibling repo
                checked out, and that must not block an unrelated commit.
      "OK"   -- ran cleanly and agrees with the manifest. Silent in normal
                output (matches the existing citation-check convention of
                "pass (silent)"), just tallied in the summary line.
    """

    def __init__(self, repo_key: str, status: str, message: str,
                 live_value: int | None = None, expected: int | None = None):
        self.repo_key = repo_key
        self.status = status
        self.message = message
        self.live_value = live_value
        self.expected = expected

    def format(self) -> str:
        return f"LIVE-CHECK {self.status} [{self.repo_key}]: {self.message}"


def _resolve_live_check_argv(source_cmd: str, source_repo: Path) -> list[str] | None:
    """Split a manifest source_cmd into argv, resolving a repo-relative
    interpreter path (e.g. ".venv/Scripts/python.exe") against source_repo.

    Returns None if the command looks like it names a specific interpreter
    path that does not actually exist on disk -- the caller treats that as
    "venv unavailable" (WARN), not a hard failure. A bare command with no
    path separator (e.g. "python", "py") is left to resolve via PATH as-is,
    since that's how source_cmd already reads for repos with no venv.
    """
    try:
        parts = shlex.split(source_cmd, posix=False)
    except ValueError:
        return None
    if not parts:
        return None
    exe = parts[0].strip('"')
    exe_path = Path(exe)
    if exe_path.is_absolute():
        if not exe_path.exists():
            return None
        return parts
    if "/" in exe or "\\" in exe:
        candidate = source_repo / exe_path
        if not candidate.exists():
            return None
        parts[0] = str(candidate)
        return parts
    # Bare command (e.g. "python", "py") -- rely on PATH.
    return parts


def live_verify_manifest(
    entries: dict[str, ManifestEntry],
    timeout: int = LIVE_CHECK_TIMEOUT_SECONDS,
) -> list[LiveCheckResult]:
    """For each manifest entry that carries a source_repo + source_cmd,
    actually run the source_cmd in that repo and compare the live "N passed"
    count against the manifest's recorded value. This is the fix for the
    self-referential-gate problem: check_proof_numbers previously only ever
    compared site citations to proof-manifest.toml, never the manifest to
    the repos it claims to describe -- so the manifest itself could rot
    (mcp-factory 152->156->179->187->...) and the gate would pass anyway.
    """
    results: list[LiveCheckResult] = []
    for key, entry in entries.items():
        if not entry.source_repo or not entry.source_cmd:
            continue  # nothing to live-check for this entry -- not an error
        source_repo = Path(entry.source_repo)
        if not source_repo.is_dir():
            results.append(LiveCheckResult(
                key, "WARN",
                f"source_repo not found on this machine ({source_repo}) -- "
                f"skipping live check (expected on CI / other clones)",
            ))
            continue

        argv = _resolve_live_check_argv(entry.source_cmd, source_repo)
        if argv is None:
            results.append(LiveCheckResult(
                key, "WARN",
                f"interpreter for source_cmd ({entry.source_cmd!r}) not found "
                f"under {source_repo} -- skipping live check (venv missing?)",
            ))
            continue

        # Every live-checked command is asked for a junitxml report (see
        # _prepare_junit_argv) -- this is what lets a repo whose plain "-q"
        # summary line is suppressed under piped/non-tty capture still be
        # live-verified reliably, instead of silently WARNing forever. The
        # scratch dir is per-entry and cleaned up as soon as this entry's
        # result is computed.
        with tempfile.TemporaryDirectory(prefix="proof_numbers_junit_") as scratch_dir_str:
            scratch_dir = Path(scratch_dir_str)
            junit_argv, junit_path = _prepare_junit_argv(argv, scratch_dir)

            try:
                # Strip inherited GIT_* env vars before invoking a DIFFERENT
                # repo's test suite. When this script runs as a real git hook,
                # git sets GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE (and friends) for
                # ITS OWN hook subprocess -- those leak into any child process
                # spawned here via plain inheritance. If the target repo's own
                # tests do git operations (e.g. mcp-factory's
                # test_workflow_runner.py calling `git ls-files`), those
                # operations get pointed at THIS repo's git internals instead of
                # the target's, and fail. Real incident 2026-07-21: 20 tests in
                # mcp-factory failed this way (215 -> 195 passed) only when
                # invoked through an actual `git commit`, never when run
                # standalone -- silent and hard to reproduce outside a real hook.
                clean_env = {k: v for k, v in os.environ.items()
                             if not k.startswith("GIT_")}
                # Per-entry env overrides (manifest "source_env" table). Real
                # use: mcp-factory's clean-checkout count (what public CI gates
                # on) differs from a bare run on the fleet machine, where
                # test_smoke_hub auto-discovers the live bot fleet -- pointing
                # MCP_FACTORY_SMOKE_ROOTS at an empty fixture dir makes the
                # live-check reproduce the clean-checkout number.
                if entry.source_env:
                    clean_env.update(entry.source_env)
                proc = subprocess.run(
                    junit_argv, cwd=source_repo, capture_output=True, text=True,
                    timeout=timeout, env=clean_env,
                )
            except subprocess.TimeoutExpired:
                results.append(LiveCheckResult(
                    key, "WARN",
                    f"source_cmd timed out after {timeout}s in {source_repo} -- "
                    f"skipping live check ({entry.source_cmd!r})",
                ))
                continue
            except OSError as exc:
                results.append(LiveCheckResult(
                    key, "WARN",
                    f"could not run source_cmd in {source_repo}: {exc} -- "
                    f"skipping live check",
                ))
                continue

            # Parsing cascade, most-to-least reliable: junitxml report, then
            # the classic "N passed" summary-line regex, then a last-resort
            # progress-dot count. See each helper's docstring for why this
            # order and why a suite whose config suppresses the summary line
            # (github-mcp/desktop-mcp/rag-mcp/bus-mcp/discord-mcp/rails-mcp/
            # vllm-ops-mcp, live-verified 2026-07-23) no longer silently
            # skips live verification.
            live_value = _parse_junit_counts(junit_path)
            parse_method = "junitxml"
            if live_value is None:
                output = f"{proc.stdout}\n{proc.stderr}"
                tail_line = None
                for line in output.splitlines():
                    if PASSED_RE.search(line):
                        tail_line = line  # keep the LAST matching line (pytest summary)
                if tail_line is not None:
                    live_value = int(PASSED_RE.search(tail_line).group(1))
                    parse_method = "summary-line"
                else:
                    live_value = _parse_dot_count(output)
                    parse_method = "dot-count"

            if live_value is None:
                results.append(LiveCheckResult(
                    key, "WARN",
                    f"could not parse a test count from source_cmd output in "
                    f"{source_repo} via junitxml, summary-line, or dot-count -- "
                    f"skipping live check",
                ))
                continue

            if live_value != entry.value:
                results.append(LiveCheckResult(
                    key, "FAIL",
                    f"manifest is stale: {key} manifest says {entry.value}, live "
                    f"repo says {live_value} (parsed via {parse_method}) -- "
                    f"refresh the manifest AND the site citations",
                    live_value=live_value, expected=entry.value,
                ))
            else:
                results.append(LiveCheckResult(
                    key, "OK",
                    f"live count {live_value} matches manifest (via {parse_method})",
                    live_value=live_value, expected=entry.value,
                ))
    return results


class ManifestValidationError(Exception):
    """Raised when proof-manifest.toml fails schema validation.

    Finding 3: previously, load_manifest() silently skipped any section that
    didn't have a lowercase "value" key (e.g. a typo'd "Value = 187"), so a
    single malformed section made the WHOLE manifest key disappear -- every
    citation that would have been checked against it silently demoted to an
    unresolved WARN, and the gate still exited 0. Fail closed instead: any
    schema violation aborts the load entirely (see load_manifest below).
    """


class ManifestEntry:
    """A validated proof-manifest.toml record.

    `value`/`source_cmd` are required by the schema (see load_manifest_entries).
    `source_repo` is optional in the schema -- entries built ad hoc in tests
    (or a future manually-seeded entry) may omit it -- but is required for the
    live-repo-verification pass in live_verify_manifest(): an entry with no
    source_repo simply can't be live-checked and is skipped (WARN), not FAIL.
    """

    def __init__(self, key: str, value: int, source_cmd: str | None = None,
                 source_repo: str | None = None,
                 source_env: dict[str, str] | None = None):
        self.key = key
        self.value = value
        self.source_cmd = source_cmd
        self.source_repo = source_repo
        self.source_env = source_env


def load_manifest_entries(path: Path = MANIFEST_PATH) -> dict[str, ManifestEntry]:
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    manifest: dict[str, ManifestEntry] = {}
    for key, entry in data.items():
        # Every top-level table in this manifest is a repo record and MUST
        # contribute a "value" (the number allowed to be cited) and a
        # "source_cmd" (how that value was actually verified) -- see this
        # file's own header comment. A missing/malformed section (a typo'd
        # field name, an empty table, a non-table entry) is not silently
        # skipped: it fails the whole load, because a silently-dropped
        # manifest key means every citation for that repo would otherwise go
        # unresolved (WARN, not FAIL) forever.
        if not isinstance(entry, dict):
            raise ManifestValidationError(
                f'proof-manifest.toml: entry "{key}" is not a table '
                f"(expected [\"{key}\"] with value/source_cmd fields)"
            )
        if "value" not in entry:
            raise ManifestValidationError(
                f'proof-manifest.toml: entry ["{key}"] is missing required '
                f'field "value" (found fields: {sorted(entry.keys())}) -- '
                f"check for a typo (e.g. \"Value\" instead of \"value\")"
            )
        if "source_cmd" not in entry:
            raise ManifestValidationError(
                f'proof-manifest.toml: entry ["{key}"] is missing required '
                f'field "source_cmd" (found fields: {sorted(entry.keys())})'
            )
        try:
            value = int(entry["value"])
        except (TypeError, ValueError) as exc:
            raise ManifestValidationError(
                f'proof-manifest.toml: entry ["{key}"]\'s "value" is not an '
                f"integer: {entry['value']!r}"
            ) from exc
        source_env = entry.get("source_env")
        if source_env is not None:
            if not isinstance(source_env, dict) or not all(
                isinstance(k, str) and isinstance(v, str)
                for k, v in source_env.items()
            ):
                raise ManifestValidationError(
                    f'proof-manifest.toml: entry ["{key}"]\'s "source_env" '
                    f"must be a table of string values (env var name -> "
                    f"value); got: {source_env!r}"
                )
        manifest[key] = ManifestEntry(
            key=key,
            value=value,
            source_cmd=entry.get("source_cmd"),
            source_repo=entry.get("source_repo"),
            source_env=source_env,
        )
    return manifest


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, int]:
    """Back-compat wrapper: value-only view of the manifest, used by the
    citation-vs-manifest scan (scan_file) which never needed source_repo."""
    return {key: e.value for key, e in load_manifest_entries(path).items()}


def _parse_int(token: str) -> int:
    return int(token.replace(",", ""))


def _iter_labelled_matches(line: str):
    """Yield non-overlapping matches for `line` across all LABEL_PATTERNS, in
    priority order. A candidate match is skipped if its span overlaps one
    already accepted from an earlier pattern, so a single citation (e.g.
    "187 passing tests") is never counted twice even though more than one
    pattern could technically match the same text."""
    accepted: list[tuple[int, int]] = []
    for pattern in LABEL_PATTERNS:
        for m in pattern.finditer(line):
            start, end = m.start(), m.end()
            if any(start < a_end and end > a_start for a_start, a_end in accepted):
                continue
            accepted.append((start, end))
            yield m


def _nearest_key_on_line(line: str, manifest_keys: list[str], approx_pos: int) -> str | None:
    """Return the manifest key on `line` whose match position is closest to approx_pos."""
    best_key = None
    best_dist = None
    for key in manifest_keys:
        for m in re.finditer(re.escape(key), line, re.IGNORECASE):
            dist = abs(m.start() - approx_pos)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_key = key
    return best_key


def _keys_on_line(line: str, manifest_keys: list[str]) -> list[str]:
    return [k for k in manifest_keys if k.lower() in line.lower()]


def _file_stem_key(path: Path, manifest_keys: list[str]) -> str | None:
    stem = path.stem
    for key in manifest_keys:
        if key.lower() == stem.lower():
            return key
    return None


def _window_key(lines: list[str], idx: int, manifest_keys: list[str]) -> str | None:
    lo = max(0, idx - WINDOW)
    hi = min(len(lines), idx + WINDOW + 1)
    best_key = None
    best_dist = None
    for i in range(lo, hi):
        if i == idx:
            continue
        keys = _keys_on_line(lines[i], manifest_keys)
        if keys:
            dist = abs(i - idx)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_key = keys[0]
    return best_key


def scan_file(path: Path, manifest: dict[str, int]) -> list[Finding]:
    findings: list[Finding] = []
    manifest_keys = list(manifest.keys())
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    for idx, line in enumerate(lines):
        line_no = idx + 1

        # Rule 3: roster idiom, e.g. "Test counts (179 mcp-factory, 50 rag-mcp, 186 options-bot)"
        if ROSTER_LINE_RE.search(line):
            paren_start = line.find("(")
            paren_end = line.rfind(")")
            segment = line[paren_start:paren_end + 1] if 0 <= paren_start < paren_end else line
            for m in ROSTER_PAIR_RE.finditer(segment):
                number = _parse_int(m.group(1))
                slug = m.group(2)
                repo_key = next((k for k in manifest_keys if k.lower() == slug.lower()), None)
                if repo_key is not None:
                    expected = manifest[repo_key]
                    verdict = "FAIL" if number != expected else None
                    if verdict:
                        findings.append(Finding(path, line_no, line, number, repo_key, verdict, expected))
                else:
                    findings.append(Finding(path, line_no, line, number, slug, "WARN"))
            # Roster line handled; still fall through in case the same line also
            # carries a PATTERN_LABELLED match elsewhere (rare) -- harmless if so,
            # PATTERN_LABELLED below re-scans the whole line independently.

        # Rule 1: only consider labelled-number matches on trigger lines.
        if not TRIGGER_RE.search(line):
            continue

        for m in _iter_labelled_matches(line):
            groups = [g for g in m.groups() if g]
            for num_str in groups:
                number = _parse_int(num_str)
                approx_pos = m.start()

                same_line_keys = _keys_on_line(line, manifest_keys)
                if len(same_line_keys) == 1:
                    repo_key = same_line_keys[0]
                elif len(same_line_keys) > 1:
                    repo_key = _nearest_key_on_line(line, same_line_keys, approx_pos)
                else:
                    repo_key = _file_stem_key(path, manifest_keys)
                    if repo_key is None:
                        repo_key = _window_key(lines, idx, manifest_keys)

                if repo_key is None:
                    # Rule 4f: no repo label anywhere nearby -- fall back to
                    # associating by value before giving up.
                    value_matches = [k for k, v in manifest.items() if v == number]
                    if len(value_matches) == 1:
                        repo_key = value_matches[0]

                if repo_key is not None and repo_key in manifest:
                    expected = manifest[repo_key]
                    if number != expected:
                        findings.append(Finding(path, line_no, line, number, repo_key, "FAIL", expected))
                    # else: matches -- silent pass
                elif repo_key is None and number not in KNOWN_NONCANONICAL_NUMBERS:
                    # Orphaned: no label, no value match, not a documented
                    # exception -- presumed drifted/uncanonical. FAIL rather
                    # than silently WARN (this is finding 1's whole point).
                    findings.append(Finding(path, line_no, line, number, None, "FAIL", None))
                else:
                    findings.append(Finding(path, line_no, line, number, repo_key, "WARN"))

    return findings


def resolve_targets(root: Path, patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(sorted(root.glob(pattern)))
    # de-dupe, keep only existing files
    seen = set()
    result = []
    for p in paths:
        if p.is_file() and p not in seen:
            seen.add(p)
            result.append(p)
    return result


def _live_check_findings(entries: dict[str, ManifestEntry]) -> tuple[list[LiveCheckResult], list[LiveCheckResult]]:
    """Run live_verify_manifest unless explicitly skipped, split into
    (fails, warns). Skipping is opt-in only (PROOF_NUMBERS_SKIP_LIVE_CHECK=1)
    -- by default every run three-way-checks live repo == manifest == site
    citations, since a silently-skipped live check is exactly how the
    self-referential-gate bug (this fix's whole reason to exist) recurs."""
    if os.environ.get(SKIP_LIVE_CHECK_ENV_VAR):
        print(f"check_proof_numbers: {SKIP_LIVE_CHECK_ENV_VAR} set -- skipping live-repo verification.")
        return [], []
    results = live_verify_manifest(entries)
    fails = [r for r in results if r.status == "FAIL"]
    warns = [r for r in results if r.status == "WARN"]
    return fails, warns


def run(root: Path = REPO_ROOT, manifest_path: Path = MANIFEST_PATH,
        target_patterns: list[str] | None = None) -> int:
    try:
        entries = load_manifest_entries(manifest_path)
    except ManifestValidationError as exc:
        print(f"check_proof_numbers: FATAL -- {exc}")
        print("check_proof_numbers: manifest is malformed; failing closed (exit 2).")
        return 2
    manifest = {key: e.value for key, e in entries.items()}
    targets = resolve_targets(root, target_patterns or DEFAULT_TARGET_GLOBS)

    all_fails: list[Finding | LiveCheckResult] = []
    all_warns: list[Finding | LiveCheckResult] = []

    for path in targets:
        for finding in scan_file(path, manifest):
            try:
                finding.file = finding.file.relative_to(root)
            except ValueError:
                pass
            if finding.verdict == "FAIL":
                all_fails.append(finding)
            else:
                all_warns.append(finding)

    live_fails, live_warns = _live_check_findings(entries)
    all_fails.extend(live_fails)
    all_warns.extend(live_warns)

    for w in all_warns:
        print(w.format())
    for f in all_fails:
        print(f.format())

    if all_fails:
        print(f"\ncheck_proof_numbers: {len(all_fails)} FAIL, {len(all_warns)} WARN")
        return 2

    print(f"check_proof_numbers: OK ({len(all_warns)} WARN, 0 FAIL)")
    return 0


def main(argv: list[str]) -> int:
    if argv:
        # Explicit file args (used by tests): scan exactly those files, manifest
        # still loaded from the real repo root unless overridden by env/caller.
        try:
            entries = load_manifest_entries(MANIFEST_PATH)
        except ManifestValidationError as exc:
            print(f"check_proof_numbers: FATAL -- {exc}")
            print("check_proof_numbers: manifest is malformed; failing closed (exit 2).")
            return 2
        manifest = {key: e.value for key, e in entries.items()}
        all_fails: list[Finding | LiveCheckResult] = []
        all_warns: list[Finding | LiveCheckResult] = []
        for arg in argv:
            path = Path(arg)
            for finding in scan_file(path, manifest):
                if finding.verdict == "FAIL":
                    all_fails.append(finding)
                else:
                    all_warns.append(finding)

        live_fails, live_warns = _live_check_findings(entries)
        all_fails.extend(live_fails)
        all_warns.extend(live_warns)

        for w in all_warns:
            print(w.format())
        for f in all_fails:
            print(f.format())
        if all_fails:
            print(f"\ncheck_proof_numbers: {len(all_fails)} FAIL, {len(all_warns)} WARN")
            return 2
        print(f"check_proof_numbers: OK ({len(all_warns)} WARN, 0 FAIL)")
        return 0
    return run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
