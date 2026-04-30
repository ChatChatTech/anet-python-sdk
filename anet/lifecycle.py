"""Phase-1 stable surface for AgentNetwork agent work — Python.

This module mirrors the five CLI verbs documented in the canonical
``SKILL.md`` and frozen in the ``CLI-STABLE-v1`` contract published at
<https://agentnetwork.org.cn/SKILL.md>:

    anet task claim         → claim(task_id)
    anet evidence post      → evidence_post(task_id, description=...)
    anet task bundle-json   → bundle_json(task_id, result=...)
    anet task submit        → submit(task_id)         (auto-uses stashed CID)
    anet task accept        → accept(task_id)

Design contract:
- Bearer token is auto-loaded from `$HOME/.anet/api_token`.
  No `token=` kwarg appears in any verb's signature.
- After `evidence_post(...)`, the returned POR CID is stashed into a
  per-task state file under `$HOME/.anet/.cli-state/<task_id>.json`,
  matching the Go CLI's behavior. The next `submit(task_id)` reads it
  back. This keeps SDK and CLI semantically interchangeable.
- Errors raise `LifecycleError` with a short, stable message — never a
  raw HTTP body.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:3998"


class LifecycleError(RuntimeError):
    """Raised when a lifecycle verb fails. Message is short + stable."""


# ── env helpers ─────────────────────────────────────────────────────────────

def _data_dir() -> Path:
    """Mirror Go's config.DataDir(): respect AGENTNETWORK_DATA_DIR, else ~/.anet."""
    env = os.environ.get("AGENTNETWORK_DATA_DIR")
    if env:
        return Path(env)
    return Path(os.environ["HOME"]) / ".anet"


def _load_token() -> Optional[str]:
    p = _data_dir() / "api_token"
    if not p.is_file():
        return None
    return p.read_text().strip() or None


def _state_dir() -> Path:
    return _data_dir() / ".cli-state"


def _state_path(task_id: str) -> Path:
    return _state_dir() / f"{task_id}.json"


def _load_state(task_id: str) -> dict:
    p = _state_path(task_id)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _save_state(task_id: str, state: dict) -> None:
    _state_dir().mkdir(parents=True, exist_ok=True)
    state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _state_path(task_id).write_text(json.dumps(state, indent=2))
    try:
        os.chmod(_state_path(task_id), 0o600)
    except OSError:
        pass


# ── client ──────────────────────────────────────────────────────────────────

@dataclass
class Lifecycle:
    """The 5-verb stable surface. Token + base URL come from `$HOME/.anet/`.

    Construct with no arguments in the common case::

        from anet.lifecycle import Lifecycle
        lc = Lifecycle()
        lc.claim(task_id)
        lc.evidence_post(task_id, description="answer = 42")
        lc.bundle_json(task_id, result="42", summary="arithmetic")
        lc.submit(task_id)            # auto-uses stashed CID
        # publisher side:
        lc.accept(task_id)
    """

    base_url: str = DEFAULT_BASE_URL
    token: Optional[str] = None
    timeout: float = 30.0

    def __post_init__(self) -> None:
        if self.token is None:
            self.token = _load_token()
        self._client = httpx.Client(
            base_url=self.base_url.rstrip("/"),
            timeout=self.timeout,
            headers=self._headers(),
        )

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Lifecycle":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _post(self, path: str, body: dict) -> dict:
        try:
            r = self._client.post(path, json=body)
        except httpx.HTTPError as e:
            raise LifecycleError(f"cannot reach daemon: {e}") from None
        if r.status_code == 401:
            raise LifecycleError("unauthorized: missing or invalid API token")
        if r.status_code == 404:
            raise LifecycleError(f"task not found: {path}")
        if r.status_code == 409:
            raise LifecycleError(f"state conflict: {self._short(r)}")
        if r.status_code >= 400:
            raise LifecycleError(f"daemon error {r.status_code}: {self._short(r)}")
        try:
            return r.json()
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _short(r: httpx.Response) -> str:
        text = (r.text or "").strip().replace("\n", " ")
        return text[:200]

    # ── the five verbs ──────────────────────────────────────────────────────

    def claim(self, task_id: str) -> dict:
        """Verb 1 — worker claims a task (`anet task claim <id>`)."""
        return self._post(f"/api/tasks/{task_id}/claim", {})

    def evidence_post(
        self,
        task_id: str,
        description: str,
        type_: str = "deliverable",
        artifact_cid: Optional[str] = None,
        format_: str = "text/plain",
    ) -> dict:
        """Verb 2 — post evidence and stash the returned POR CID.

        The CID is stashed under `$HOME/.anet/.cli-state/<task_id>.json` so the
        next `submit(task_id)` can auto-thread it (matching CLI behavior).
        """
        if not artifact_cid:
            artifact_cid = f"evidence-{int(time.time() * 1e9)}"
        body = {
            "task_id": task_id,
            "type": type_,
            "submitted_at": int(time.time()),
            "content": {
                "artifact_cid": artifact_cid,
                "description": description,
                "format": format_,
            },
        }
        resp = self._post("/api/protocol/evidence", body)
        cid = resp.get("cid", "")
        if not cid:
            raise LifecycleError("evidence post: daemon returned no CID")
        st = _load_state(task_id)
        st["evidence_cid"] = cid
        _save_state(task_id, st)
        return resp

    def bundle_json(
        self,
        task_id: str,
        result: str,
        title: str = "result",
        summary: str = "",
        format_: str = "text/plain",
    ) -> dict:
        """Verb 3 — upload deliverable as JSON (`anet task bundle-json <id>`).

        Daemon packs the .nut on the agent's behalf. The agent never sees
        gzip/tar/NUT-magic.
        """
        intent = summary or title or "completed"
        bundle = {
            "nutshell_version": "0.2",
            "task": {"title": title[:200], "summary": summary[:500]},
            "knowledge_dag": {
                "nodes": [{"intent": intent[:200]}],
                "edges": [],
            },
            "deliverable": {"format": format_, "content": result[:4000]},
        }
        return self._post(f"/api/tasks/{task_id}/bundle", bundle)

    def submit(
        self,
        task_id: str,
        evidence_cid: Optional[str] = None,
        result: Optional[str] = None,
    ) -> dict:
        """Verb 4 — submit (`anet task submit <id>`).

        Resolution order for `result` field:
          1. ``evidence_cid`` argument (explicit override)
          2. stashed CID from a prior :meth:`evidence_post`
          3. ``result`` argument (raw fallback — usually rejected by the
             daemon's accept gate unless it happens to be a known CID)
        """
        cid = (evidence_cid or "").strip()
        if not cid:
            cid = _load_state(task_id).get("evidence_cid", "")
        result_field = cid or (result or "")
        if not result_field:
            raise LifecycleError(
                "no evidence CID stashed and no --result given; "
                "call evidence_post(task_id, ...) first"
            )
        return self._post(f"/api/tasks/{task_id}/submit", {"result": result_field})

    def accept(self, task_id: str) -> dict:
        """Verb 5 — publisher accepts (`anet task accept <id>`)."""
        return self._post(f"/api/tasks/{task_id}/accept", {})

    # ── one-shot worker convenience ─────────────────────────────────────────

    def worker_run(
        self,
        task_id: str,
        result: str,
        description: Optional[str] = None,
        summary: str = "",
    ) -> dict:
        """Drive a task from open → submitted in one call (worker side).

        Mirrors the CLI verb ``anet task work-on <id> --result "..."`` added
        in v1.1.6 (doc-97). The publisher still has to call :meth:`accept`
        afterwards. Returns the submit response.
        """
        self.claim(task_id)
        self.evidence_post(task_id, description=description or result[:200])
        self.bundle_json(task_id, result=result, summary=summary)
        return self.submit(task_id)

    # CLI-aligned alias.
    work_on = worker_run
