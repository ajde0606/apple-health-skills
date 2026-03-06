#!/usr/bin/env python3
"""Compatibility launcher for users who run `python scripts/setup.sh` by habit.

Runs the real setup shell script with bash.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    setup_sh = repo_root / "scripts" / "setup.sh"
    raise SystemExit(subprocess.call(["bash", str(setup_sh), *sys.argv[1:]]))
