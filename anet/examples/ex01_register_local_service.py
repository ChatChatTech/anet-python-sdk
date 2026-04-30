"""Example 1 — register a local HTTP service with the P2P gateway.

What you'll see:
- A 30-line script registers a local echo backend as a free P2P service named
  ``echo-sdk``, then unregisters cleanly.
- ``anet svc list`` (or ``SvcClient.list()``) will see it between register/
  unregister.

Prerequisites (in two terminals):

    # term-1: start the daemon (writes ~/.anet/api_token on first run)
    anet daemon

    # term-2: start the echo backend on :7000 (provided by this SDK)
    python -m anet.examples._echo_backend

Then run this file:

    python -m anet.examples.ex01_register_local_service

Expected output (truncated):

    ✓ registered echo-sdk (ans.published=True meta.attempted=True)
    list now shows: ['echo-sdk']
    health: [{'name': 'echo-sdk', 'status': 'healthy', 'code': 200, ...}]
    meta:   {'name': 'echo-demo', 'version': '0.1.0', ...}
    ✓ unregistered, list now shows: []
"""

from __future__ import annotations

from anet.svc import SvcClient


def main() -> None:
    with SvcClient() as svc:
        resp = svc.register(
            name="echo-sdk",
            endpoint="http://127.0.0.1:7000",
            paths=["/echo", "/health", "/meta"],
            modes=["rr"],
            free=True,
            tags=["demo", "echo"],
            description="echo-sdk: minimal example registered via Python SDK",
            health_check="/health",
            meta_path="/meta",
        )
        print(
            f"✓ registered {resp.get('name')} "
            f"(ans.published={(resp.get('ans') or {}).get('published')} "
            f"meta.attempted={(resp.get('meta_probe') or {}).get('attempted')})"
        )

        names = [e["name"] for e in svc.list()]
        print(f"list now shows: {names}")

        print(f"health: {svc.health()}")
        print(f"meta:   {svc.meta('echo-sdk')}")

        svc.unregister("echo-sdk")
        names = [e["name"] for e in svc.list()]
        print(f"✓ unregistered, list now shows: {names}")


if __name__ == "__main__":
    main()
