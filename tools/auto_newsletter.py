#!/usr/bin/env python3
"""Build and send the daily web development and AI news digest when new items appear."""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".local/newsletter_state.json"
WORK = ROOT / ".tmp"
RECIPIENT = "hs6423590@gmail.com"


def canonical_url(value):
    parts = urlsplit(value)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    WORK.mkdir(exist_ok=True)
    previous = json.loads(STATE.read_text()) if STATE.exists() else {"urls": []}
    seen = set(previous.get("urls", []))
    fresh_by_topic = []
    for topic in ("web development React Next.js releases security", "artificial intelligence AI research model releases policy"):
        slug = "web" if topic.startswith("web") else "ai"
        artifact = WORK / f"auto_research_{slug}.json"
        run(sys.executable, "tools/research_topic.py", topic, "--topic-type", "news", "--time-range", "day", "--limit", "10", "--output", str(artifact))
        data = json.loads(artifact.read_text())
        items = []
        for item in data.get("results", []):
            url = item.get("url")
            if url and canonical_url(url) not in seen:
                item["url"] = canonical_url(url)
                items.append(item)
        if items:
            fresh_by_topic.append((slug, data, items))

    if not fresh_by_topic:
        print("No new news sources today; no email sent.")
        return

    all_urls = set(seen)
    sections = []
    sources = []
    labels = {"web": "Web development", "ai": "Artificial intelligence"}
    for slug, data, items in fresh_by_topic:
        summaries = []
        for item in items:
            all_urls.add(item["url"])
        for item in items[:5]:
            url = item["url"]
            title = item.get("title") or url
            snippet = (item.get("content") or item.get("snippet") or "").strip()
            summaries.append(f"[{title}]({url})\n\n{snippet}" if snippet else f"[{title}]({url})")
            sources.append({"title": title, "url": url})
        sections.append({"heading": labels[slug], "body": "\n\n".join(summaries)})

    today = date.today().isoformat()
    newsletter = {
        "subject": f"Web Dev & AI Brief | {today}",
        "preheader": "New developments in web development and AI, with links to the original sources.",
        "title": "Web development and AI: daily brief",
        "intro": "A source-linked roundup of new developments found in today’s news search.",
        "sections": sections,
        "closing": "Follow the source links for full details and context.",
        "sources": sources,
        "infographic_prompt": "Create a clear, professional 16:9 newsletter infographic summarizing these developments: " + "; ".join(f"{s['heading']}: {s['body'][:350]}" for s in sections) + ". Use a clean technology editorial style, concise labels, and no invented statistics, unsupported claims, or logos.",
    }
    newsletter_path = WORK / "auto_newsletter.json"
    newsletter_path.write_text(json.dumps(newsletter, ensure_ascii=False, indent=2) + "\n")
    image_path = WORK / "auto_infographic.png"
    run(sys.executable, "tools/generate_infographic.py", "--prompt", newsletter["infographic_prompt"], "--output", str(image_path))
    newsletter["infographic"] = str(image_path.relative_to(ROOT))
    newsletter_path.write_text(json.dumps(newsletter, ensure_ascii=False, indent=2) + "\n")
    html_path = WORK / "auto_newsletter.html"
    run(sys.executable, "tools/render_newsletter.py", str(newsletter_path), "--output", str(html_path))
    run(sys.executable, "tools/send_newsletter.py", str(newsletter_path), "--to", RECIPIENT, "--html", str(html_path), "--confirm-send", "--yes")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"urls": sorted(all_urls), "last_sent": today}, indent=2) + "\n")


if __name__ == "__main__":
    main()
