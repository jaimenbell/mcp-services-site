"""Tests for js/click-track.js -- the `?ref=` click-attribution beacon.

Executes the REAL, checked-in js/click-track.js source inside an actual
Node.js process with browser globals (window, navigator, fetch, Blob) stubbed
-- this is a production-shape positive control (CLAUDE.md: "a positive
control not run in the production shape is not a positive control"), not a
test of a reimplementation. Only the CLICK_BEACON_URL literal is substituted
per test case via a regex that pins the exact checked-in line; if that line
ever changes shape, the substitution assertion below fires loudly instead of
silently testing stale code.

Both directions of the check are covered:
  1. FIRES -- CLICK_BEACON_URL non-empty AND `?ref=` present: a beacon goes
     out with the right endpoint, transport (sendBeacon, or fetch/POST as the
     documented fallback), and payload shape (ref/path/ts).
  2. STAYS SILENT -- CLICK_BEACON_URL empty (the actual checked-in state,
     which is the historically inert case this whole task exists to fix) OR
     no `?ref=` on the URL: nothing is sent. The read-and-stash-to-
     sessionStorage side effect still runs regardless (documented behavior),
     since it's independent of whether an endpoint is configured.

Requires a `node` binary on PATH; skips (never fails) if absent, per the
repo's own _bash_path()-style skip pattern in test_check_beacon_coverage.py.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CLICK_TRACK_JS = REPO_ROOT / "js" / "click-track.js"

# Pins the exact checked-in declaration line. If js/click-track.js changes
# this line's shape, this regex stops matching and _run_click_track's assert
# fires -- a loud break, never a silent pass against stale substituted code.
CLICK_BEACON_URL_RE = re.compile(r'var CLICK_BEACON_URL = "[^"]*";[^\n]*')

HARNESS_TEMPLATE = """
"use strict";
var __calls = { sendBeacon: null, fetch: null };

global.Blob = function (parts, opts) {
  this.__body = parts.join("");
  this.type = (opts && opts.type) || "";
};

Object.defineProperty(globalThis, "navigator", {
  value: %(navigator_obj)s,
  writable: true,
  configurable: true,
});

global.fetch = function (url, opts) {
  __calls.fetch = {
    url: url,
    method: opts.method,
    body: opts.body,
    headers: opts.headers,
  };
  return Promise.resolve().catch(function () {});
};

var __store = {};
global.window = {
  location: { search: %(query)s, pathname: "/case-studies/example.html" },
  sessionStorage: {
    setItem: function (k, v) { __store[k] = v; },
    getItem: function (k) { return __store[k]; },
  },
};

%(script)s

process.stdout.write(JSON.stringify({ calls: __calls, stored: __store }));
"""

NAVIGATOR_WITH_SEND_BEACON = """{
  sendBeacon: function (url, blob) {
    __calls.sendBeacon = { url: url, body: blob.__body, type: blob.type };
    return true;
  },
}"""

NAVIGATOR_WITHOUT_SEND_BEACON = "{}"


def _require_node():
    if shutil.which("node") is None:
        pytest.skip("node not found on PATH -- cannot execute click-track.js for real")


def _patched_source(beacon_url: str) -> str:
    source = CLICK_TRACK_JS.read_text(encoding="utf-8")
    match = CLICK_BEACON_URL_RE.search(source)
    assert match is not None, (
        "js/click-track.js no longer matches the expected "
        '\'var CLICK_BEACON_URL = "...";\' declaration -- update '
        "CLICK_BEACON_URL_RE in this test file to match the new shape"
    )
    return CLICK_BEACON_URL_RE.sub(f'var CLICK_BEACON_URL = "{beacon_url}";', source, count=1)


def _run_click_track(tmp_path: Path, query: str, beacon_url: str, has_send_beacon: bool = True) -> dict:
    _require_node()
    patched = _patched_source(beacon_url)
    harness = HARNESS_TEMPLATE % {
        "query": json.dumps(query),
        "script": patched,
        "navigator_obj": NAVIGATOR_WITH_SEND_BEACON if has_send_beacon else NAVIGATOR_WITHOUT_SEND_BEACON,
    }
    script_path = tmp_path / "harness.js"
    script_path.write_text(harness, encoding="utf-8")
    result = subprocess.run(
        ["node", str(script_path)], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, f"node harness crashed:\n{result.stdout}\n{result.stderr}"
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# POSITIVE CONTROL, direction 1: the beacon FIRES.
# ---------------------------------------------------------------------------


def test_beacon_fires_via_sendbeacon_when_url_configured_and_ref_present(tmp_path):
    out = _run_click_track(tmp_path, "?ref=abc123def", "https://click-beacon.example.workers.dev")
    call = out["calls"]["sendBeacon"]
    assert call is not None, "sendBeacon must be called when CLICK_BEACON_URL is set and ?ref= is present"
    assert out["calls"]["fetch"] is None, "sendBeacon path must not also use fetch"
    assert call["url"] == "https://click-beacon.example.workers.dev"
    assert call["type"] == "application/json"
    payload = json.loads(call["body"])
    assert payload["ref"] == "abc123def"
    assert payload["path"] == "/case-studies/example.html"
    assert "ts" in payload and payload["ts"], "payload must carry a timestamp"
    assert out["stored"]["jnb_ref"] == "abc123def"


def test_beacon_fires_and_extracts_ref_among_other_query_params(tmp_path):
    out = _run_click_track(tmp_path, "?utm_source=x&ref=zz9&other=1", "https://beacon.example/hit")
    call = out["calls"]["sendBeacon"]
    assert call is not None
    payload = json.loads(call["body"])
    assert payload["ref"] == "zz9"


def test_beacon_fires_via_fetch_fallback_when_sendbeacon_unavailable(tmp_path):
    """Documented fallback path (js/click-track.js lines ~52-59): older/
    restricted browsers without navigator.sendBeacon still get a POST via
    fetch, with the same endpoint/payload shape and correct method/headers."""
    out = _run_click_track(
        tmp_path, "?ref=fallback1", "https://click-beacon.example.workers.dev",
        has_send_beacon=False,
    )
    call = out["calls"]["fetch"]
    assert call is not None, "fetch fallback must fire when navigator.sendBeacon is unavailable"
    assert out["calls"]["sendBeacon"] is None
    assert call["url"] == "https://click-beacon.example.workers.dev"
    assert call["method"] == "POST"
    assert call["headers"]["Content-Type"] == "application/json"
    payload = json.loads(call["body"])
    assert payload["ref"] == "fallback1"


# ---------------------------------------------------------------------------
# POSITIVE CONTROL, direction 2: the beacon STAYS SILENT.
# ---------------------------------------------------------------------------


def test_beacon_silent_when_url_empty_the_actual_checked_in_state(tmp_path):
    """This is the repo's ACTUAL checked-in CLICK_BEACON_URL value (empty
    string) -- the historically inert case this whole task exists to make
    deployable. Must never fire, even though ?ref= is present and the ref is
    still stashed to sessionStorage for a later session (documented, ref-
    independent-of-endpoint behavior)."""
    out = _run_click_track(tmp_path, "?ref=abc123", "")
    assert out["calls"]["sendBeacon"] is None
    assert out["calls"]["fetch"] is None
    assert out["stored"]["jnb_ref"] == "abc123"


def test_beacon_silent_when_no_ref_even_with_url_configured(tmp_path):
    out = _run_click_track(tmp_path, "", "https://click-beacon.example.workers.dev")
    assert out["calls"]["sendBeacon"] is None
    assert out["calls"]["fetch"] is None
    assert "jnb_ref" not in out["stored"]


def test_beacon_silent_when_ref_param_present_but_empty(tmp_path):
    out = _run_click_track(tmp_path, "?ref=", "https://click-beacon.example.workers.dev")
    assert out["calls"]["sendBeacon"] is None
    assert out["calls"]["fetch"] is None
    assert "jnb_ref" not in out["stored"]


def test_beacon_silent_when_both_url_and_ref_absent(tmp_path):
    out = _run_click_track(tmp_path, "", "")
    assert out["calls"]["sendBeacon"] is None
    assert out["calls"]["fetch"] is None
    assert "jnb_ref" not in out["stored"]


# ---------------------------------------------------------------------------
# Regression guard: the repo's REAL checked-in CLICK_BEACON_URL must stay
# empty -- no automated change (or accidental commit) may pre-fill a real
# endpoint. Filling it in is explicitly the operator's one manual step.
# ---------------------------------------------------------------------------


def test_real_checked_in_beacon_url_is_empty():
    source = CLICK_TRACK_JS.read_text(encoding="utf-8")
    match = CLICK_BEACON_URL_RE.search(source)
    assert match is not None
    assert 'var CLICK_BEACON_URL = "";' in match.group(0), (
        "CLICK_BEACON_URL must stay empty in the checked-in file -- the "
        "deployed Worker URL is the operator's one manual step, documented "
        "in scripts/click-beacon-DEPLOY.md, never something an automated "
        "change should fill in"
    )
