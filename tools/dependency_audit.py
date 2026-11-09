#!/usr/bin/env python3
"""Query public OSV using only locked public package names/versions; never runtime state."""

import json
from pathlib import Path
import tomllib
import urllib.request

root = Path(__file__).resolve().parents[1]
packages = [
    p
    for p in tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))["package"]
    if p.get("source", {}).get("registry")
]
body = json.dumps(
    {
        "queries": [
            {"package": {"name": p["name"], "ecosystem": "PyPI"}, "version": p["version"]}
            for p in packages
        ]
    }
).encode()
request = urllib.request.Request(
    "https://api.osv.dev/v1/querybatch", data=body, headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(request, timeout=30) as response:
    results = json.load(response)["results"]
if len(results) != len(packages):
    raise SystemExit("OSV returned an incomplete result; audit not passed")
findings = [
    {
        "package": p["name"],
        "version": p["version"],
        "advisories": [v["id"] for v in r.get("vulns", [])],
    }
    for p, r in zip(packages, results)
    if r.get("vulns") or r.get("next_page_token")
]
if findings:
    print(json.dumps(findings))
    raise SystemExit(1)
print(f"OSV PASS: {len(packages)} locked public Python packages; zero reported findings")
