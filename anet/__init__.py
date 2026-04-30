"""AgentNetwork Python SDK — REST client for the AgentNetwork daemon API.

Usage:
    from anet import AgentNetwork
    cn = AgentNetwork()                          # default http://127.0.0.1:3998
    status = cn.status()
    board = cn.tasks_list()

Phase-1 stable surface (CLI-aligned 5-verb lifecycle):
    from anet.lifecycle import Lifecycle
    with Lifecycle() as lc:
        lc.claim(task_id)
        lc.evidence_post(task_id, description="answer = 42")
        lc.bundle_json(task_id, result="42")
        lc.submit(task_id)        # auto-uses stashed CID
        # publisher:
        lc.accept(task_id)
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

import httpx

from anet.lifecycle import Lifecycle, LifecycleError  # re-export
from anet.svc import (  # re-export
    AuthMissingError,
    SSEEvent,
    SvcAPIError,
    SvcClient,
    SvcError,
)


class AgentNetworkError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"AgentNetwork API error {status}: {body}")


class AgentNetwork:
    """Synchronous REST client for the AgentNetwork daemon."""

    def __init__(self, base_url: str = "http://127.0.0.1:3998"):
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base, timeout=30.0)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AgentNetwork":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # -- helpers --

    def _get(self, path: str, **params: Any) -> Any:
        r = self._client.get(path, params={k: v for k, v in params.items() if v is not None})
        if r.status_code >= 400:
            raise AgentNetworkError(r.status_code, r.text)
        return r.json()

    def _post(self, path: str, body: Any = None) -> Any:
        r = self._client.post(path, json=body)
        if r.status_code >= 400:
            raise AgentNetworkError(r.status_code, r.text)
        return r.json()

    # -- Status --

    def status(self) -> dict:
        return self._get("/api/status")

    def peers(self) -> list:
        return self._get("/api/peers")

    def shutdown(self) -> dict:
        return self._post("/api/shutdown")

    # -- Credits --

    def credits_balance(self) -> dict:
        return self._get("/api/credits/balance")

    def credits_transfer(self, to: str, amount: float, memo: str | None = None) -> dict:
        return self._post("/api/credits/transfer", {"to": to, "amount": amount, "memo": memo})

    def credits_events(self) -> list:
        return self._get("/api/credits/events")

    # -- Tasks --

    def tasks_list(self) -> dict:
        return self._get("/api/tasks/board")

    def tasks_create(self, title: str, reward: float = 0, **kw: Any) -> dict:
        return self._post("/api/tasks", {"title": title, "reward": reward, **kw})

    def tasks_get(self, task_id: str) -> dict:
        return self._get(f"/api/tasks/{quote(task_id)}")

    def tasks_claim(self, task_id: str) -> dict:
        return self._post(f"/api/tasks/{quote(task_id)}/claim")

    def tasks_submit(self, task_id: str, result: str) -> dict:
        return self._post(f"/api/tasks/{quote(task_id)}/submit", {"result": result})

    def tasks_accept(self, task_id: str) -> dict:
        return self._post(f"/api/tasks/{quote(task_id)}/accept")

    def tasks_reject(self, task_id: str, reason: str = "") -> dict:
        return self._post(f"/api/tasks/{quote(task_id)}/reject", {"reason": reason})

    def tasks_cancel(self, task_id: str) -> dict:
        return self._post(f"/api/tasks/{quote(task_id)}/cancel")

    # -- ANS --

    def ans_resolve(self, name: str) -> dict:
        return self._get("/api/ans/resolve", name=name)

    def ans_register(self, name: str, **kw: Any) -> dict:
        return self._post("/api/ans/register", {"name": name, **kw})

    def ans_records(self) -> list:
        return self._get("/api/ans/records")

    def ans_lookup(self, tags: list[str], namespace: str | None = None, limit: int | None = None) -> dict:
        return self._get("/api/ans/lookup", tags=",".join(tags), namespace=namespace, limit=limit)

    def ans_search(self, q: str, namespace: str | None = None, limit: int | None = None) -> dict:
        return self._get("/api/ans/search", q=q, namespace=namespace, limit=limit)

    def ans_unregister(self, name: str) -> dict:
        return self._post("/api/ans/unregister", {"name": name})

    def ans_transfer(self, name: str, to_owner: str) -> dict:
        return self._post("/api/ans/transfer", {"name": name, "to_owner": to_owner})

    def ans_auctions(self) -> dict:
        return self._get("/api/ans/auctions")

    def ans_auction(self, name: str) -> dict:
        return self._get(f"/api/ans/auctions/{quote(name)}")

    def ans_bid(self, name: str, amount: float, bidder: str) -> dict:
        return self._post(f"/api/ans/auctions/{quote(name)}/bid", {"bidder": bidder, "amount": amount})

    # -- Discovery --

    def discover(self, name: str | None = None, skills: list[str] | None = None,
                 q: str | None = None, limit: int | None = None, min_rep: float | None = None) -> dict:
        params: dict[str, Any] = {}
        if name:
            params["name"] = name
        if skills:
            params["skills"] = ",".join(skills)
        if q:
            params["q"] = q
        if limit:
            params["limit"] = limit
        if min_rep:
            params["min_rep"] = min_rep
        return self._get("/api/discover", **params)

    def discover_dns_sd(self, domain: str) -> dict:
        return self._get("/api/discover/dns-sd", domain=domain)

    def agent_card(self) -> dict:
        return self._get("/.well-known/agent-card.json")

    # -- DM --

    def dm_send(self, to: str, message: str) -> dict:
        return self._post("/api/dm/send", {"to": to, "message": message})

    def dm_inbox(self) -> list:
        return self._get("/api/dm/inbox")

    def dm_thread(self, peer: str) -> list:
        return self._get(f"/api/dm/thread/{quote(peer)}")

    # -- Reputation --

    def reputation_get(self, did: str) -> dict:
        return self._get(f"/api/reputation/{quote(did)}")

    def reputation_attest(self, did: str, score: float, comment: str = "") -> dict:
        return self._post("/api/reputation/attest", {"did": did, "score": score, "comment": comment})

    # -- Knowledge --

    def knowledge_feed(self) -> list:
        return self._get("/api/knowledge/feed")

    def knowledge_publish(self, content: Any) -> dict:
        return self._post("/api/knowledge/publish", content)

    def knowledge_search(self, query: str) -> dict:
        return self._post("/api/knowledge/search", {"query": query})

    # -- Topics --

    def topics_list(self) -> list:
        return self._get("/api/topics")

    def topics_join(self, name: str) -> dict:
        return self._post("/api/topics", {"name": name})

    def topics_leave(self, name: str) -> dict:
        return self._post(f"/api/topics/{quote(name)}/leave")

    def topics_send(self, name: str, message: str) -> dict:
        return self._post(f"/api/topics/{quote(name)}/send", {"message": message})

    def topics_messages(self, name: str) -> list:
        return self._get(f"/api/topics/{quote(name)}/messages")

    # -- ADP --

    def adp_cards(self) -> dict:
        return self._get("/api/adp/cards")

    def adp_publish(self, card: dict) -> dict:
        return self._post("/api/adp/publish", card)

    # -- Observability --

    def traces(self) -> list:
        return self._get("/api/traces")

    def metrics(self) -> dict:
        return self._get("/api/metrics")
