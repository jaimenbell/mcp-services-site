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

import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "proof-manifest.toml"

# Files scanned by default when this script is run with no arguments (the
# pre-commit hook uses this list). Callers (tests) may pass explicit paths
# instead.
DEFAULT_TARGET_GLOBS = [
    "index.html",
    "GO-LIVE.md",
    "README.md",
    "case-studies/*.html",
    "case-studies/*.md",
]

TRIGGER_RE = re.compile(r"\b(?:tests?|passing|passed)\b", re.IGNORECASE)

NUM = r"(\d{1,3}(?:,\d{3})+|\d+)"

# "<N> [+ <M>] <label>" -- number(s) immediately followed by a labelling word.
PATTERN_LABELLED = re.compile(
    rf"{NUM}(?:\s*\+\s*{NUM})?\s+(?:passing\s+tests|passed\s+tests|passing|passed|tests?)\b",
    re.IGNORECASE,
)

# "<N> <word> <label>" -- number-before-label with ONE intervening word, e.g.
# "mcp-factory ships with 200 unit tests". The negative lookahead keeps this
# from double-matching plain "<N> passing tests" (already caught by
# PATTERN_LABELLED above) by refusing to treat a label word itself as the
# "intervening word".
PATTERN_LABELLED_GAP = re.compile(
    rf"{NUM}\s+(?!(?:passing|passed|tests?)\b)[a-zA-Z]+\s+"
    rf"(?:passing\s+tests|passed\s+tests|passing|passed|tests?)\b",
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
# When adding a new named-but-untracked proof-number callout to the site,
# add its value(s) here (with a comment explaining why it's untracked) or it
# will start FAILing the commit gate as a suspicious orphaned number.
KNOWN_NONCANONICAL_NUMBERS = {186, 2806, 283}


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


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, int]:
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    manifest = {}
    for key, entry in data.items():
        if isinstance(entry, dict) and "value" in entry:
            manifest[key] = int(entry["value"])
    return manifest


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


def run(root: Path = REPO_ROOT, manifest_path: Path = MANIFEST_PATH,
        target_patterns: list[str] | None = None) -> int:
    manifest = load_manifest(manifest_path)
    targets = resolve_targets(root, target_patterns or DEFAULT_TARGET_GLOBS)

    all_fails: list[Finding] = []
    all_warns: list[Finding] = []

    for path in targets:
        for finding in scan_file(path, manifest):
            rel_path = finding.file
            try:
                finding.file = finding.file.relative_to(root)
            except ValueError:
                pass
            if finding.verdict == "FAIL":
                all_fails.append(finding)
            else:
                all_warns.append(finding)

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
        root = REPO_ROOT
        manifest = load_manifest(MANIFEST_PATH)
        all_fails: list[Finding] = []
        all_warns: list[Finding] = []
        for arg in argv:
            path = Path(arg)
            for finding in scan_file(path, manifest):
                if finding.verdict == "FAIL":
                    all_fails.append(finding)
                else:
                    all_warns.append(finding)
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
