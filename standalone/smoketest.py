"""Smoke test — stdlib only, no network required, no threads started.
STRESS_TEST.md Fix #3: first automated regression net for the platform.

Runs in the Docker build (and manually: `python smoketest.py`): forces
synthetic bars, populates the bar cache directly, then calls every no-arg
view and asserts each returns a JSON-serializable dict/list without raising.
Views that normally fetch the network tolerate failure by design (they
return error payloads) — a short socket timeout keeps the build fast.
"""
import json
import os
import socket
import sys
import time

os.environ["QUANTA_SYNTH_BARS"] = "1"
os.environ["QUANTA_DATA"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smoke_data")
socket.setdefaulttimeout(6)

import quanta  # noqa: E402  (env must be set before import)

# Populate bars without network or background threads.
for sym in quanta.BAR_UNIVERSE:
    with quanta._bars_lock:
        quanta._bars[sym] = quanta.synth_daily(sym)
        quanta._bars_meta[sym] = {"updated": time.time(), "source": "synth"}

VIEWS = [
    "sector_scores", "signals", "rotation", "macro_view", "regime_view",
    "probabilities_view", "analogs_view", "research_view", "opportunities_view",
    "factors_view", "registry_view", "allocation_view", "calibration_view",
    "scorecard_view", "assumptions_view", "drift_view", "counterfactual_view",
    "priorities_view", "committee_view", "hypotheses_view", "replication_view",
    "exp11_view", "integrity_view", "congress_view", "congress_reg_view",
    "government_view", "director_view", "decisions_view", "positions_view",
    "market_summary", "agents_view", "ops_view",
]

failures = []
for name in VIEWS:
    fn = getattr(quanta, name, None)
    if fn is None:
        failures.append("%s: MISSING (renamed? update smoketest.py)" % name)
        continue
    t0 = time.time()
    try:
        v = fn()
        if not isinstance(v, (dict, list)):
            raise AssertionError("returned %s, expected dict/list" % type(v).__name__)
        json.dumps(v, default=str)
        print("ok   %-22s %5.1fs" % (name, time.time() - t0))
    except Exception as e:  # noqa: BLE001 — the whole point is catching anything
        failures.append("%s: %r" % (name, e))
        print("FAIL %-22s %r" % (name, e))

# targeted invariants beyond "doesn't crash"
try:
    sc = quanta.sector_scores()
    assert len(sc["sectors"]) == 11, "expected 11 sector rows"
    assert "alphaStatus" in sc, "descriptive disclosure missing from scores payload"
    d = quanta.director_view()
    assert d["backlog"], "director backlog empty"
    assert d["topRecommendation"]["priorityScore"] is not None
    ai = quanta.ai_status()
    assert "safety" in ai, "AI safety statement missing"
    print("ok   invariants")
except Exception as e:  # noqa: BLE001
    failures.append("invariants: %r" % e)
    print("FAIL invariants %r" % e)

if failures:
    print("\nSMOKE TEST FAILED (%d):" % len(failures))
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("\nSMOKE TEST PASSED (%d views)" % len(VIEWS))
