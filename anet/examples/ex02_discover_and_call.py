"""Example 2 — discover a service by skill, then call it (rr mode).

What you'll see:
- The script picks a peer that exposes the ``echo`` skill (any peer registered
  with ``tags=['echo', ...]``), then issues one POST /echo call.
- This works **across two daemons**: u1 registers, u2 discovers + calls. To
  test it locally, boot two ``anet daemon`` instances on different
  ``ANET_HOME`` / ``ANET_API_PORT`` so they discover each other via mDNS.

Prerequisites:

    # both daemons running and meshed (mDNS or explicit bootstrap_peers)
    # AT LEAST ONE peer registered an `echo` service (see ex01)

Run:

    python -m anet.examples.ex02_discover_and_call

Expected output:

    found 1 peer(s) for skill=echo
      - peer 12D3KooW…    1 service(s)
        * echo-sdk [http/rr] echo-sdk: minimal …
    calling echo-sdk on 12D3KooW…/echo …
    HTTP 200
    body: {'echo': {'msg': 'hi from sdk'}, 'caller_did': 'did:key:…'}
"""

from __future__ import annotations

import sys

from anet.svc import SvcClient


def main(skill: str = "echo") -> int:
    with SvcClient() as svc:
        peers = svc.discover(skill=skill)
        if not peers:
            print(
                f"no peers expose skill={skill!r}. run ex01 on a second daemon "
                "(or pass a different skill on the command line) and retry.",
                file=sys.stderr,
            )
            return 1
        print(f"found {len(peers)} peer(s) for skill={skill}")
        for p in peers:
            print(f"  - peer {p['peer_id'][:18]}…  {len(p['services'])} service(s)")
            for s in p["services"]:
                modes = ",".join(s.get("modes") or [])
                print(f"    * {s['name']} [{s.get('transport')}/{modes}] {s.get('description', '')}")

        target = peers[0]
        svc_name = target["services"][0]["name"]
        print(f"\ncalling {svc_name} on {target['peer_id'][:18]}…/echo …")
        resp = svc.call(
            target["peer_id"],
            svc_name,
            "/echo",
            method="POST",
            body={"msg": "hi from sdk"},
        )
        print(f"HTTP {resp.get('status')}")
        print(f"body: {resp.get('body')}")
    return 0


if __name__ == "__main__":
    sk = sys.argv[1] if len(sys.argv) > 1 else "echo"
    raise SystemExit(main(sk))
