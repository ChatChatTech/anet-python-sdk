"""Unit tests for anet.svc.SvcClient.

Uses ``httpx.MockTransport`` so the daemon is not required. Mirrors the
contract documented by ``anet svc help`` and the canonical ``/api/svc/*``
REST handlers in the AgentNetwork daemon.
"""

from __future__ import annotations

import json
import os
import sys

import httpx
import pytest

# Make the SDK importable when running directly out of the repo (no install).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from anet.svc import (  # noqa: E402
    AuthMissingError,
    SSEEvent,
    SvcAPIError,
    SvcClient,
    _iter_sse,
)


@pytest.fixture
def mock_client():
    """Returns a (factory, calls_log) tuple. factory(handler) → SvcClient."""
    calls: list[httpx.Request] = []

    def factory(handler):
        def transport_handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return handler(request)

        c = httpx.Client(
            base_url="http://127.0.0.1:3998",
            transport=httpx.MockTransport(transport_handler),
            headers={"Authorization": "Bearer test-token"},
        )
        client = SvcClient(token="test-token", client=c)
        return client

    return factory, calls


# ──────────────────────────────────────────────────────────────────────────
# auth resolution
# ──────────────────────────────────────────────────────────────────────────


def test_auth_missing_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("ANET_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(AuthMissingError):
        SvcClient()


def test_auth_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ANET_TOKEN", "env-token")
    monkeypatch.setenv("HOME", str(tmp_path))
    c = SvcClient()
    assert c.token == "env-token"
    c.close()


def test_auth_from_disk(monkeypatch, tmp_path):
    monkeypatch.delenv("ANET_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".anet").mkdir()
    (tmp_path / ".anet" / "api_token").write_text("disk-token\n")
    c = SvcClient()
    assert c.token == "disk-token"
    c.close()


# ──────────────────────────────────────────────────────────────────────────
# register
# ──────────────────────────────────────────────────────────────────────────


def test_register_normalises_paths_and_cost(mock_client):
    factory, calls = mock_client

    def handler(req):
        body = json.loads(req.content)
        assert body["paths"] == [{"prefix": "/echo"}, {"prefix": "/health"}]
        assert body["cost_model"] == {"free": True}
        assert body["modes"] == ["rr"]
        assert body["tags"] == ["demo"]
        assert body["transport"] == "http"
        return httpx.Response(200, json={"ok": True, "name": body["name"]})

    c = factory(handler)
    resp = c.register(
        name="echo", endpoint="http://127.0.0.1:7000",
        paths=["/echo", "/health"], free=True, tags=["demo"],
    )
    assert resp == {"ok": True, "name": "echo"}
    assert calls[0].url.path == "/api/svc/register"


def test_register_paid_cost_dimensions(mock_client):
    factory, _ = mock_client

    def handler(req):
        body = json.loads(req.content)
        assert body["cost_model"] == {"per_call": 10, "per_kb": 2}
        return httpx.Response(200, json={"ok": True, "name": body["name"]})

    c = factory(handler)
    c.register(
        name="paid", endpoint="http://127.0.0.1:7000",
        paths=["/x"], per_call=10, per_kb=2,
    )


def test_register_surfaces_errors_join(mock_client):
    """CP2: errors.Join multi-error should arrive as SvcAPIError.errors."""
    factory, _ = mock_client

    def handler(_req):
        return httpx.Response(400, json={
            "error": "invalid request",
            "errors": ["name is required", "endpoint is required", "modes is required"],
        })

    c = factory(handler)
    with pytest.raises(SvcAPIError) as exc:
        c.register(name="", endpoint="", paths=[], free=True)
    assert exc.value.status == 400
    assert exc.value.errors == [
        "name is required",
        "endpoint is required",
        "modes is required",
    ]
    msg = str(exc.value)
    assert "name is required" in msg


def test_register_dict_path_passthrough(mock_client):
    factory, _ = mock_client

    def handler(req):
        body = json.loads(req.content)
        assert body["paths"] == [{"prefix": "/echo", "methods": ["POST"]}]
        return httpx.Response(200, json={"ok": True, "name": "x"})

    c = factory(handler)
    c.register(
        name="x", endpoint="http://127.0.0.1:7000",
        paths=[{"prefix": "/echo", "methods": ["POST"]}], free=True,
    )


# ──────────────────────────────────────────────────────────────────────────
# list / show / unregister
# ──────────────────────────────────────────────────────────────────────────


def test_list_show_unregister(mock_client):
    factory, calls = mock_client

    entries = [
        {"name": "a", "endpoint": "http://127.0.0.1:1"},
        {"name": "b", "endpoint": "http://127.0.0.1:2"},
    ]

    def handler(req):
        if req.method == "GET" and req.url.path == "/api/svc":
            return httpx.Response(200, json=entries)
        if req.method == "POST" and req.url.path == "/api/svc/unregister":
            return httpx.Response(200, json={"ok": True})
        raise AssertionError(f"unexpected {req.method} {req.url.path}")

    c = factory(handler)
    assert c.list() == entries
    assert c.show("a") == entries[0]
    with pytest.raises(Exception):
        c.show("missing")
    assert c.unregister("a") == {"ok": True}


# ──────────────────────────────────────────────────────────────────────────
# discover
# ──────────────────────────────────────────────────────────────────────────


def test_discover_by_peer_passes_envelope(mock_client):
    factory, _ = mock_client

    def handler(req):
        assert req.url.params["peer_id"] == "PEER1"
        return httpx.Response(200, json={"status": 200, "body": [{"name": "echo"}]})

    c = factory(handler)
    out = c.discover(peer_id="PEER1")
    assert out["status"] == 200


def test_discover_by_skill_unwraps_results(mock_client):
    factory, _ = mock_client

    def handler(req):
        assert req.url.params["skill"] == "llm"
        return httpx.Response(200, json={
            "skill": "llm", "count": 1,
            "results": [{
                "peer_id": "PEER1",
                "owner_did": "did:key:abc",
                "ans_name": "agent://svc/llm-XYZ",
                "services": [{"name": "llm-svc", "modes": ["server-stream"]}],
            }],
        })

    c = factory(handler)
    peers = c.discover(skill="llm")
    assert isinstance(peers, list) and len(peers) == 1
    assert peers[0]["peer_id"] == "PEER1"


def test_discover_requires_filter(mock_client):
    factory, _ = mock_client
    c = factory(lambda _r: httpx.Response(500))
    with pytest.raises(Exception):
        c.discover()


# ──────────────────────────────────────────────────────────────────────────
# call
# ──────────────────────────────────────────────────────────────────────────


def test_call_basic(mock_client):
    factory, _ = mock_client

    def handler(req):
        body = json.loads(req.content)
        assert body == {
            "peer_id": "P1", "service": "echo", "method": "POST",
            "path": "/echo", "body": {"hi": 1},
        }
        assert req.url.params.get("passthrough_status") is None
        return httpx.Response(200, json={"status": 200, "body": {"echo": {"hi": 1}}})

    c = factory(handler)
    resp = c.call("P1", "echo", "/echo", body={"hi": 1})
    assert resp["status"] == 200
    assert resp["body"]["echo"] == {"hi": 1}


def test_call_passthrough_status_unwraps_4xx_envelope(mock_client):
    """CP5: with passthrough_status the daemon mirrors upstream status to the
    outer HTTP response, but the JSON envelope is the same — SDK should still
    return it instead of raising."""
    factory, _ = mock_client

    def handler(req):
        assert req.url.params["passthrough_status"] == "1"
        return httpx.Response(403, json={"status": 403, "error": "forbidden"})

    c = factory(handler)
    resp = c.call("P1", "echo", "/forbidden", passthrough_status=True)
    assert resp == {"status": 403, "error": "forbidden"}


def test_call_passthrough_5xx_without_envelope_raises(mock_client):
    factory, _ = mock_client

    def handler(_req):
        return httpx.Response(502, json={"message": "bad gateway"})

    c = factory(handler)
    with pytest.raises(SvcAPIError):
        c.call("P1", "echo", "/x", passthrough_status=True)


def test_call_string_body_encoded_as_string(mock_client):
    factory, _ = mock_client

    def handler(req):
        body = json.loads(req.content)
        assert body["body"] == "raw text"
        return httpx.Response(200, json={"status": 200, "body": "ok"})

    c = factory(handler)
    c.call("P1", "echo", "/echo", body="raw text")


def test_call_json_string_body_decoded(mock_client):
    factory, _ = mock_client

    def handler(req):
        body = json.loads(req.content)
        assert body["body"] == {"x": 1}
        return httpx.Response(200, json={"status": 200, "body": {}})

    c = factory(handler)
    c.call("P1", "echo", "/echo", body='{"x": 1}')


# ──────────────────────────────────────────────────────────────────────────
# health / meta / audit
# ──────────────────────────────────────────────────────────────────────────


def test_health(mock_client):
    factory, _ = mock_client
    h = [{"name": "echo", "status": "healthy", "code": 200, "latency_ms": 3}]
    c = factory(lambda _r: httpx.Response(200, json=h))
    assert c.health() == h


def test_meta_returns_json(mock_client):
    factory, _ = mock_client
    c = factory(lambda _r: httpx.Response(200, json={"name": "echo", "version": "0.1.0"}))
    assert c.meta("echo") == {"name": "echo", "version": "0.1.0"}


def test_audit_unwraps_calls(mock_client):
    factory, _ = mock_client
    payload = {
        "count": 2, "service": "", "limit": 50,
        "calls": [
            {"service": "echo", "status": 200, "cost": 0},
            {"service": "echo", "status": 403, "cost": 0},
        ],
    }
    c = factory(lambda _r: httpx.Response(200, json=payload))
    rows = c.audit(limit=50)
    assert isinstance(rows, list)
    assert [r["status"] for r in rows] == [200, 403]


# ──────────────────────────────────────────────────────────────────────────
# ws_url
# ──────────────────────────────────────────────────────────────────────────


def test_ws_url_format(monkeypatch, tmp_path):
    monkeypatch.setenv("ANET_TOKEN", "x")
    monkeypatch.setenv("HOME", str(tmp_path))
    c = SvcClient(base_url="http://127.0.0.1:3998")
    assert c.ws_url("chat") == "ws://127.0.0.1:3998/api/svc/ws/chat"
    c2 = SvcClient(base_url="https://daemon.example.com")
    assert c2.ws_url("chat space") == "wss://daemon.example.com/api/svc/ws/chat%20space"
    c.close()
    c2.close()


# ──────────────────────────────────────────────────────────────────────────
# SSE parser
# ──────────────────────────────────────────────────────────────────────────


class _FakeResp:
    def __init__(self, lines):
        self._lines = lines

    def iter_lines(self):
        return iter(self._lines)


def test_iter_sse_basic():
    lines = [
        "event: status",
        "data: 200",
        "",
        "data: hello",
        "",
        "data: world",
        "",
        "event: done",
        "data: end",
        "",
    ]
    events = list(_iter_sse(_FakeResp(lines)))
    assert events == [
        SSEEvent("status", "200"),
        SSEEvent("message", "hello"),
        SSEEvent("message", "world"),
        SSEEvent("done", "end"),
    ]
    assert events[-1].is_terminal


def test_iter_sse_skips_comments_and_merges_multiline_data():
    lines = [
        ": this is a comment, ignore",
        "event: message",
        "data: line1",
        "data: line2",
        "",
    ]
    events = list(_iter_sse(_FakeResp(lines)))
    assert events == [SSEEvent("message", "line1\nline2")]
