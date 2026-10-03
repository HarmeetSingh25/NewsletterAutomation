#!/usr/bin/env python3
"""Add or remove email subscribers and their newsletter topics."""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBSCRIBERS = ROOT / ".local/subscribers.json"
TOPICS = ("web", "ai")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    add = actions.add_parser("add", help="Subscribe an address to selected topics")
    add.add_argument("email")
    add.add_argument("topics", nargs="+", choices=TOPICS)
    remove = actions.add_parser("remove", help="Unsubscribe an address")
    remove.add_argument("email")
    parser.add_argument("--list", action="store_true", help="List subscribers after updating")
    args = parser.parse_args()

    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", args.email):
        parser.error("provide a valid email address")
    SUBSCRIBERS.parent.mkdir(parents=True, exist_ok=True)
    subscribers = json.loads(SUBSCRIBERS.read_text(encoding="utf-8")) if SUBSCRIBERS.exists() else []
    subscribers = [item for item in subscribers if item.get("email", "").lower() != args.email.lower()]
    if args.action == "add":
        subscribers.append({"email": args.email, "topics": list(dict.fromkeys(args.topics))})
        print(f"Subscribed {args.email} to: {', '.join(dict.fromkeys(args.topics))}")
    else:
        print(f"Removed {args.email} from the subscriber list")
    SUBSCRIBERS.write_text(json.dumps(subscribers, indent=2) + "\n", encoding="utf-8")
    if args.list:
        print(json.dumps(subscribers, indent=2))


if __name__ == "__main__":
    main()
