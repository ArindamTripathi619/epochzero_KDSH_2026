# Python 3.14 Environment Recovery: "Arch Linux Breakthrough"

This document records the steps taken to stabilize the epochzero project on a high-alpha Python 3.14 environment on Arch Linux.

## 1. The Beartype Conflict
Python 3.14 introduced changes to how type hints are resolved, which triggered a `BeartypeDecorHintNonpepException` in Pathway's internal type-checking decorators.

### Error Trace:
```python
beartype.roar.BeartypeDecorHintNonpepException: function 
pathway.internals.schema.schema_from_types() parameter "_name" 
type hint str | None either PEP-noncompliant or currently unsupported
```

### The "Surgical Lock" Solution:
Instead of rewriting Pathway's internals, we implemented a **monkey-patch** at the very top of `main.py` before any Pathway imports:

```python
import sys
from unittest.mock import MagicMock

# Block beartype to prevent PEP-noncompliant crashes on Python 3.14
mock_beartype = MagicMock()
mock_beartype.beartype = lambda x: x  # Identity decorator
sys.modules['beartype'] = mock_beartype
sys.modules['beartype.roar'] = MagicMock()
```

This bypasses the strict runtime type-checking that was blocking the entire pipeline.

## 2. Dependency Resolution (The Binary-Only Rule)
Arch Linux's rolling nature combined with Python 3.14 caused several packages (e.g., `pyarrow`, `pydantic-core`) to attempt building from source, which failed due to missing v3.14-specific build flags or C-header incompatibilities.

### Mitigation Strategy:
We enforced **binary-only wheels** for critical infrastructure:

```bash
pip install --upgrade --only-binary=:all: \
    pyarrow \
    pydantic-core \
    pathway[llm]
```

This ensures the environment uses pre-compiled C-extensions that are compatible with the stable parts of the v3.14 runtime.

## 3. Persistent Virtual Environment
The virtual environment was consolidated at `/home/DevCrewX/Projects/epochzero_KDSH_2026/.venv`.

### Re-verification Command:
```bash
python main.py --help
```
If this returns the Pathway help menu without a beartype crash, the environment is successfully "locked."
