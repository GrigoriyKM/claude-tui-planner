"""Quest TUI package — ensure quest library is importable."""

import sys as _sys
from pathlib import Path as _Path

_QUEST_ROOT = str(_Path.home() / ".claude" / "quest")
if _QUEST_ROOT not in _sys.path:
    _sys.path.insert(0, _QUEST_ROOT)
