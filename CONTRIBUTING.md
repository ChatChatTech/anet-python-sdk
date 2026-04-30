# Contributing to anet (Python SDK)

Thanks for taking the time to improve the SDK.

## Where development happens

This repository (`github.com/ChatChatTech/anet-python-sdk`) is a **one-way
mirror** of the canonical source tree maintained inside ChatChatTech's main
AgentNetwork repository. The mirror is refreshed by an internal sync script
that snapshots the SDK directory and force-pushes here.

That has two practical consequences for contributors:

1. **Direct PRs are very welcome.** Open them against `main`. Maintainers will
   review and discuss here, then re-apply the change inside the canonical
   repo and the next sync run will land it back here. Your commit attribution
   in the PR thread is preserved for the changelog; the mirrored commit
   itself will be a squashed snapshot.
2. **`main` is force-pushed.** Don't fork from `main` and expect the SHA to
   stay stable across days. Branch off `main` for your PR, push to your fork,
   and rebase if asked.

## Local dev loop

```bash
# clone & set up
git clone https://github.com/ChatChatTech/anet-python-sdk.git
cd anet-python-sdk

python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# run offline tests (no daemon required)
pytest -q tests/test_svc.py
```

The integration tests under `tests/test_lifecycle_live.py` need a running
`anet daemon`; they are intentionally **excluded** from CI in this public
repo because the harness lives inside the closed source tree.

## Style

- Code: PEP-8, 4 spaces, line length ~100.
- Imports: stdlib → third-party → local; one group per blank line.
- Public surface should have type hints and a one-paragraph docstring.
- No new runtime deps without a strong reason. The SDK currently only
  depends on `httpx`, and that bar is intentional.
- Don't introduce `print()` calls in library code. Tests / examples can
  print freely.

## Releasing (maintainers only)

Tagging is done from this repository:

- `v1.x.y-test1` → triggers `publish-testpypi.yml` (TestPyPI)
- `v1.x.y`       → triggers `publish-pypi.yml`     (PyPI, after the workflow
  is enabled)

Both flows use OIDC Trusted Publishing, so there are no PyPI tokens stored
anywhere in the repo or GitHub Actions secrets.

## Code of Conduct

Be excellent to each other. We follow the
[Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
