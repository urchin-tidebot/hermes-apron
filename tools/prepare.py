#!/usr/bin/env python3
"""Materialize public pinned sources in TMPDIR; never inspect a user's Hermes install."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "server": (
        "https://github.com/apron-chat/apron-server-go.git",
        "cefba0193cf5cf8407dfb47c0970b9a26e6c1b8c",
    ),
    "hermes": (
        "https://github.com/NousResearch/hermes-agent.git",
        "6cff782b8d081a0ed382eaf75c432d452cd452cc",
    ),
    "web": (
        "https://github.com/apron-chat/apron-web.git",
        "95a6314e2629f0965dd61fa688f7eb1b4abbd26c",
    ),
}


def prepare(name):
    patch = ROOT / (
        "patches/closed-enrollment.patch" if name == "server" else "patches/frontend.patch"
    )
    digest = (
        hashlib.sha256(patch.read_bytes()).hexdigest()[:16]
        if name in {"server", "web"}
        else "source"
    )
    base = Path(os.environ["TMPDIR"]) / (
        "hermes-apron-" + name + "-" + PINS[name][1][:12] + "-" + digest
    )
    # A process-level lock makes concurrent builds safe. No secrets stored here.
    import fcntl

    lock = base.with_suffix(".lock")
    with lock.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        marker = base / ".prepared"
        if not marker.exists():
            base.mkdir(mode=0o700, exist_ok=True)

            def git(*args):
                subprocess.run(["git", "-C", str(base), *args], check=True, stdout=sys.stderr)

            git("init", "-q")
            git("fetch", "--quiet", "--depth", "1", PINS[name][0], PINS[name][1])
            git("checkout", "--quiet", "--detach", "FETCH_HEAD")
            if name in {"server", "web"}:
                git("apply", "--check", str(patch))
                git("apply", str(patch))
            marker.touch(mode=0o600)
        actual = subprocess.check_output(
            ["git", "-C", str(base), "rev-parse", "HEAD"], text=True
        ).strip()
        if actual != PINS[name][1]:
            raise RuntimeError("upstream pin mismatch")
    return base


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "server"
    base = prepare(name)
    if name == "server":
        work = base / "go.work"
        content = (
            "go 1.27.3\n\nuse (\n "
            + json.dumps(str(ROOT))
            + "\n "
            + json.dumps(str(base))
            + "\n)\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=base, delete=False
        ) as staged:
            staged.write(content)
        os.replace(staged.name, work)
        print(work)
    else:
        print(base)
