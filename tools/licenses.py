#!/usr/bin/env python3
"""Collect runtime Go module notices in a scratch build bundle, without private source paths."""

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
output = Path(sys.argv[1]) / "licenses"
output.mkdir(parents=True, exist_ok=True)
raw = subprocess.check_output(
    [str(ROOT / "tools/go"), "list", "-deps", "-json", "./cmd/apron-home"], cwd=ROOT, text=True
)
decoder = json.JSONDecoder()
modules = {}
while raw.strip():
    item, end = decoder.raw_decode(raw.lstrip())
    raw = raw.lstrip()[end:]
    module = item.get("Module")
    if module:
        modules[module["Path"]] = module
goroot = Path(subprocess.check_output([str(ROOT / "tools/go"), "env", "GOROOT"], text=True).strip())
stdlib_notice = goroot / "LICENSE"
if not stdlib_notice.is_file():
    # Nix's split GOROOT omits this file; retain the official pinned notice.
    stdlib_notice = ROOT / "third_party/go-LICENSE"
(output / "Go-LICENSE").write_bytes(stdlib_notice.read_bytes())
notices = []
for name, module in sorted(modules.items()):
    directory = Path(module["Dir"])
    copied = []
    for file in sorted(directory.iterdir()):
        if file.is_file() and file.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
            target = output / (name.replace("/", "__") + "__" + file.name)
            target.write_bytes(file.read_bytes())
            copied.append(target.name)
    if not copied:
        raise SystemExit("missing runtime module license: " + name)
    notices.append(
        {
            "module": name,
            "version": module.get("Version", "workspace pin; see provenance"),
            "notices": copied,
        }
    )
(output / "index.json").write_text(json.dumps(notices, indent=2) + "\n", encoding="utf-8")
# Include the project's audited patch and source provenance by reference, never runtime state.
print(f"Collected notices for {len(notices)} runtime Go modules")
