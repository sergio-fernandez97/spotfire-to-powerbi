#!/usr/bin/env python3
"""PostToolUse hook: keep generated TMDL valid while Claude works.

- Edit/Write of ``out/<analysis>/translations.json`` -> ``dxp2pbi tmdl`` (regenerate + validate)
- Edit/Write of a ``.tmdl`` inside a ``*.SemanticModel`` -> ``dxp2pbi validate``

On failure the report goes to stderr with exit code 2, which Claude Code shows to Claude.
Written for the system python3 (3.9+): no third-party imports.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    file_path = (event.get("tool_input") or {}).get("file_path") or ""
    if not file_path:
        return 0

    path = Path(file_path)
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
    if path.suffix == ".tmdl" and any(part.endswith(".SemanticModel") for part in path.parts):
        command = ["validate", str(path)]
    elif path.name == "translations.json" and (path.parent / "spec.json").exists():
        command = ["tmdl", str(path.parent)]
    else:
        return 0

    try:
        proc = subprocess.run(
            ["uv", "run", "--quiet", "--project", str(project / "dxp2pbi"), "dxp2pbi", *command],
            capture_output=True, text=True, cwd=str(project), timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(f"dxp2pbi hook could not run: {exc}\n")
        return 0  # never block Claude because the tool itself is unavailable

    if proc.returncode != 0:
        sys.stderr.write(f"dxp2pbi {command[0]} failed:\n{proc.stdout}{proc.stderr}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
