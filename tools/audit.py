#!/usr/bin/env python3
"""Content/secret tripwires, including every added commit. Not a security certification."""

import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "provider credential": rb"(?:sk-(?:proj-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16})",
    "private IPv4": rb"\b(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b",
    "private hostname": rb"https?://[A-Za-z0-9_.-]+\.(?:lan|local)(?:[:/\s]|$)",
    "JWT": rb"eyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}",
}
BAD_NAMES = {".env", "server.db", "inbox.db", "credentials.json", "auth.json", "config.toml"}
BAD_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".pem", ".key", ".upload", ".jsonl"}


def inspect(name, data, label):
    path = Path(name)
    if (
        path.name in BAD_NAMES
        or path.suffix in BAD_SUFFIXES
        or any(part in {".codex", "node_modules", "uploads", "runtime"} for part in path.parts)
    ):
        raise SystemExit(f"audit: forbidden runtime/state path in {label}: {name}")
    for what, pattern in PATTERNS.items():
        if re.search(pattern, data):
            # Report location/category only, never secret contents.
            raise SystemExit(f"audit: {what} in {label}: {name}")


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    count = 0
    if args.source_only:
        files = [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
    else:
        names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")
        files = [ROOT / n.decode() for n in names if n and (ROOT / n.decode()).is_file()]
    for file in files:
        inspect(str(file.relative_to(ROOT)), file.read_bytes(), "working tree")
        count += 1
    commits = [] if args.source_only else git("rev-list", "b899490..HEAD").decode().split()
    for commit in commits:
        for name in git("ls-tree", "-r", "--name-only", commit).decode().splitlines():
            inspect(name, git("show", f"{commit}:{name}"), "added history")
    print(
        f"Content audit PASS: {count} source files; {len(commits)} added commits. Runtime artifacts and logs require separate canary checks."
    )


if __name__ == "__main__":
    main()
