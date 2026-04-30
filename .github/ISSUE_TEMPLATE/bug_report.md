---
name: Bug report
about: Something is broken in the anet Python SDK
title: "[bug] "
labels: bug
assignees: ''
---

## Describe the bug
A clear and concise description of what the bug is.

## To reproduce
Minimal Python snippet that triggers the bug. Please show the smallest possible
example — ideally something we can copy-paste and run.

```python
from anet.svc import SvcClient
# ...
```

## Expected behaviour
What you expected to happen.

## Actual behaviour
What actually happened. Paste the full traceback if any.

```
Traceback (most recent call last):
  ...
```

## Environment
- SDK version: `python -c "import anet; print(getattr(anet, '__version__', 'unknown'))"` or `pip show agentnetwork | grep Version`
- Python version: `python --version`
- OS: e.g. macOS 14.5 / Ubuntu 22.04
- `anet daemon` version: `anet --version` (if relevant)
- Daemon running locally? yes / no

## Additional context
Add any other context about the problem here.
