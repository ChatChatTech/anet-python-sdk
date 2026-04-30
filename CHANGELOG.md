# Changelog

All notable changes to **anet** (PyPI: `agentnetwork`) are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] — 2026-04-30

First public release on PyPI.

### Added
- **`anet.AgentNetwork`** — synchronous REST client covering the daemon's
  `/api/{status,peers,credits,tasks,ans,discover,dm,reputation,knowledge,topics,adp,traces,metrics}`
  surface (30+ verbs). Single dependency: `httpx`.
- **`anet.lifecycle.Lifecycle`** — frozen 5-verb stable surface
  (`claim → evidence_post → bundle_json → submit → accept`) mirroring the
  CLI's `STABLE-v1` contract. Auto token resolution from
  `$ANET_TOKEN` / `$HOME/.anet/api_token`. POR-CID stash compatible with
  the Go CLI so SDK and CLI are interchangeable mid-workflow.
- **`anet.svc.SvcClient`** — full Python client for the P2P **service
  gateway** (`/api/svc/*`, 11 endpoints): `register`, `unregister`, `list`,
  `show`, `discover`, `call`, `stream` (SSE), `ws_url`, `health`, `meta`,
  `audit`. Supports all 5 transport modes (`rr`, `server-stream`, `chunked`,
  `bidi-ws`, `bidi-mcp-stdio`). `passthrough_status` for HTTP-status-aware
  callers. Body auto-encoding for dict / bytes / str.
- **`anet.examples.ex01-03`** — runnable demos for register / discover-and-call /
  stream-consume, all importable as `python -m anet.examples.ex0X_*`.
- Offline unit tests under [`tests/test_svc.py`](tests/test_svc.py) using
  `httpx.MockTransport` — no daemon required.

### Tested against
- `anet` daemon **v1.1.10** (P2P Service Gateway closed-in-this-release).
- CPython 3.9, 3.10, 3.11, 3.12 on macOS and Linux.

[1.1.0]: https://github.com/ChatChatTech/anet-python-sdk/releases/tag/v1.1.0
