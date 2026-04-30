"""Example 3 — consume a streaming service via SSE.

What you'll see:
- Find a peer that exposes a server-stream service (e.g. an LLM proxy or a
  ticker), and print each SSE frame as it arrives.
- ``SvcClient.stream(...)`` yields ``SSEEvent(event, data)`` until either a
  ``done`` or an ``error`` terminal event arrives.

Prerequisites:

    # both daemons running
    # u1 has registered a service with modes=['server-stream']
    # (any SSE backend: LLM proxy, ticker, log tailer, …)

Run:

    python -m anet.examples.ex03_stream_consume <skill> [<path>]

Default skill is ``llm`` and default path is ``/v1/chat/stream``.

Expected output:

    streaming llm-svc on 12D3KooW…/v1/chat/stream …
    [status]  200
    [message] {"delta":"hello"}
    [message] {"delta":" world"}
    ...
    [done]    end
"""

from __future__ import annotations

import sys

from anet.svc import SvcClient


def main(skill: str = "llm", path: str = "/v1/chat/stream") -> int:
    with SvcClient() as svc:
        peers = svc.discover(skill=skill)
        if not peers:
            print(f"no peers expose skill={skill!r}", file=sys.stderr)
            return 1
        target = peers[0]
        svc_name = target["services"][0]["name"]
        print(f"streaming {svc_name} on {target['peer_id'][:18]}…{path} …")

        for ev in svc.stream(
            target["peer_id"],
            svc_name,
            path,
            method="POST",
            body={"prompt": "say hi", "max_tokens": 32},
            mode="server-stream",
        ):
            print(f"[{ev.event:8s}] {ev.data}")
            if ev.is_terminal:
                break
    return 0


if __name__ == "__main__":
    sk = sys.argv[1] if len(sys.argv) > 1 else "llm"
    pa = sys.argv[2] if len(sys.argv) > 2 else "/v1/chat/stream"
    raise SystemExit(main(sk, pa))
