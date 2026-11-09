"""Explicit local send-only test/operator entry point; no gateway or model startup."""

import argparse
import asyncio
import json
from types import SimpleNamespace
from .delivery import standalone_sender


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--room")
    parser.add_argument("--thread")
    parser.add_argument("--message", required=True)
    args = parser.parse_args()
    with open(args.config, encoding="utf-8") as file:
        config = SimpleNamespace(extra=json.load(file))
    result = asyncio.run(standalone_sender(config, args.room, args.message, thread_id=args.thread))
    print(json.dumps(result))
    raise SystemExit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
