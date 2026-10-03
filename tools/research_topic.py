#!/usr/bin/env python3
"""Search the web with Tavily and save source results for newsletter drafting."""

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

def load_tavily_key():
    """Read only the requested key from .env without displaying its value."""
    import os

    if os.getenv("TAVILY_API_KEY"):
        return os.environ["TAVILY_API_KEY"]
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "TAVILY_API_KEY":
                return value.strip().strip("\"'")
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topic", help="Topic to research")
    parser.add_argument("--limit", type=int, default=10, help="Maximum results (default: 10)")
    parser.add_argument("--topic-type", choices=("general", "news", "finance"), default="general", help="Tavily search category")
    parser.add_argument("--time-range", choices=("day", "week", "month", "year"), help="Restrict results by recency")
    parser.add_argument("--output", type=Path, default=ROOT / ".tmp/research.json")
    args = parser.parse_args()
    api_key = load_tavily_key()
    if not api_key:
        parser.error("TAVILY_API_KEY is missing; add it to .env")
    payload = json.dumps({
            "query": args.topic,
            "max_results": args.limit,
            "topic": args.topic_type,
            "search_depth": "basic",
            "include_published_date": True,
            **({"time_range": args.time_range} if args.time_range else {}),
        }).encode("utf-8")
    request = Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            data = json.load(response)
    except HTTPError as error:
        raise SystemExit(f"Tavily returned HTTP {error.code}: {error.read().decode('utf-8', errors='replace')}") from error
    except URLError as error:
        raise SystemExit(f"Could not reach Tavily: {error.reason}") from error
    results = data.get("results", [])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"topic": args.topic, "answer": data.get("answer"), "results": results}, indent=2), encoding="utf-8")
    print(f"Saved {len(results)} results to {args.output}")


if __name__ == "__main__":
    main()
