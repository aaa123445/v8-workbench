#!/usr/bin/env python3
"""Portable completion hook: JSON stdin {cwd}; never reads conversation transcripts."""

import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    try:
        raw = sys.stdin.read(65537)
        if len(raw) > 65536:
            raise ValueError("Hook input is too large")
        event = json.loads(raw or "{}")
        if event.get("stop_hook_active"):
            return
        root = Path(event.get("cwd") or os.getcwd()).resolve()
        # Only the explicit working directory is enabled; do not discover parent opt-ins.
        config = root / ".teamkb" / "config.json"
        if (
            not config.exists()
            or json.loads(config.read_text()).get("enabled") is not True
        ):
            return
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.wb",
                "agent",
                "complete",
                "--project",
                str(root),
            ],
            capture_output=True,
            text=True,
            timeout=75,
        )
        if result.returncode:
            print(
                "TeamKB: submission failed; check candidate and client configuration.",
                file=sys.stderr,
            )
        else:
            data = json.loads(result.stdout)
            print("TeamKB: " + str(data.get("status", "completed")), file=sys.stderr)
    except (ValueError, OSError, subprocess.TimeoutExpired):
        print(
            "TeamKB: completion processing failed; run wb agent complete manually.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
