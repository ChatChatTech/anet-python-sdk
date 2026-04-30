"""Live integration test: SDK 5-verb lifecycle against running harness.

Skipped automatically if the harness daemons aren't reachable. Run manually:

    HOME=/tmp/anet-harness/node2 \
      .venv/bin/python -m pytest sdk/python/tests/test_lifecycle_live.py -v
"""
from __future__ import annotations

import os
import time
import uuid

import httpx
import pytest

# Make the SDK importable when running directly out of the repo (no install).
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from anet.lifecycle import Lifecycle, LifecycleError  # noqa: E402


HARNESS_BASE = {
    1: "http://127.0.0.1:13801",
    2: "http://127.0.0.1:13802",
    3: "http://127.0.0.1:13803",
}
HARNESS_HOME = {
    1: "/tmp/anet-harness/node1",
    2: "/tmp/anet-harness/node2",
    3: "/tmp/anet-harness/node3",
}


def _alive(base: str) -> bool:
    try:
        return httpx.get(base + "/api/status", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


def _read_token(home: str) -> str:
    p = os.path.join(home, ".anet", "api_token")
    with open(p) as f:
        return f.read().strip()


def _switch_home(node: int):
    os.environ["HOME"] = HARNESS_HOME[node]


@pytest.fixture(scope="module", autouse=True)
def require_harness():
    if not (_alive(HARNESS_BASE[1]) and _alive(HARNESS_BASE[2])):
        pytest.skip("harness nodes 1+2 not reachable")


def test_5_verb_lifecycle_end_to_end():
    # ── publisher (node1) creates a task via raw HTTP (CLI / Lifecycle does not
    # currently expose `publish` — it's outside the Phase-1 stable surface) ──
    pub_token = _read_token(HARNESS_HOME[1])
    title = f"[sdk-test] {uuid.uuid4().hex[:8]}"
    r = httpx.post(
        HARNESS_BASE[1] + "/api/tasks",
        headers={"Authorization": f"Bearer {pub_token}", "Content-Type": "application/json"},
        json={"title": title, "reward": 200, "description": "live SDK test"},
        timeout=10.0,
    )
    assert r.status_code in (200, 201), r.text
    task_id = r.json()["id"]

    # Allow a moment for the task to propagate to node2's view.
    time.sleep(2)

    # ── worker (node2) drives all 4 worker verbs through the SDK ──
    _switch_home(2)
    worker = Lifecycle(base_url=HARNESS_BASE[2])
    try:
        worker.claim(task_id)
        ev = worker.evidence_post(task_id, description="sdk lifecycle smoke")
        assert "cid" in ev and ev["cid"], "evidence_post should return a CID"
        worker.bundle_json(task_id, result="42", summary="answer")
        sub = worker.submit(task_id)  # MUST auto-thread the stashed CID
        assert sub.get("has_bundle") is True
    finally:
        worker.close()

    # ── publisher accepts via SDK ──
    _switch_home(1)
    publisher = Lifecycle(base_url=HARNESS_BASE[1])
    try:
        publisher.accept(task_id)
    finally:
        publisher.close()

    # ── verify final state ──
    final = httpx.get(
        HARNESS_BASE[1] + f"/api/tasks/{task_id}",
        headers={"Authorization": f"Bearer {pub_token}"},
        timeout=5.0,
    ).json()
    assert final["state"] == "accepted", f"final state was {final['state']}"


def test_submit_without_evidence_raises():
    """Calling submit() before evidence_post() must give a short, stable error."""
    _switch_home(2)
    lc = Lifecycle(base_url=HARNESS_BASE[2])
    try:
        with pytest.raises(LifecycleError) as ei:
            lc.submit("00000000-0000-0000-0000-000000000000")
        msg = str(ei.value).lower()
        assert "no evidence cid" in msg or "task not found" in msg
    finally:
        lc.close()


def test_worker_run_one_shot():
    """The worker_run() convenience composes the 4 worker verbs in one call."""
    pub_token = _read_token(HARNESS_HOME[1])
    title = f"[sdk-test-oneshot] {uuid.uuid4().hex[:8]}"
    r = httpx.post(
        HARNESS_BASE[1] + "/api/tasks",
        headers={"Authorization": f"Bearer {pub_token}", "Content-Type": "application/json"},
        json={"title": title, "reward": 200, "description": "live oneshot"},
        timeout=10.0,
    )
    assert r.status_code in (200, 201), r.text
    task_id = r.json()["id"]
    time.sleep(2)

    _switch_home(2)
    worker = Lifecycle(base_url=HARNESS_BASE[2])
    try:
        sub = worker.worker_run(task_id, result="oneshot=ok", summary="oneshot")
        assert sub.get("has_bundle") is True
    finally:
        worker.close()

    _switch_home(1)
    publisher = Lifecycle(base_url=HARNESS_BASE[1])
    try:
        publisher.accept(task_id)
    finally:
        publisher.close()

    final = httpx.get(
        HARNESS_BASE[1] + f"/api/tasks/{task_id}",
        headers={"Authorization": f"Bearer {pub_token}"},
        timeout=5.0,
    ).json()
    assert final["state"] == "accepted"
