#!/usr/bin/env python3
"""Build and send the daily web development and AI news digest when new items appear."""

import json
import hashlib
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".local/newsletter_state.json"
WORK = ROOT / ".tmp"
RECIPIENT = "hs6423590@gmail.com"
SUBSCRIBERS = ROOT / ".local/subscribers.json"
TOPICS = {"web": "Web development", "ai": "Artificial intelligence"}


def canonical_url(value):
    parts = urlsplit(value)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def load_subscribers():
    api_url = os.getenv("NEWSLETTER_SIGNUP_API_URL")
    if api_url:
        api_token = os.getenv("SUBSCRIBER_API_TOKEN", "")
        if not api_token:
            raise ValueError("SUBSCRIBER_API_TOKEN is required with NEWSLETTER_SIGNUP_API_URL")
        request = Request(api_url.rstrip("/") + "/api/subscribers", headers={"Authorization": f"Bearer {api_token}"})
        with urlopen(request, timeout=30) as response:
            data = json.load(response)
    else:
        subscribers_json = os.getenv("NEWSLETTER_SUBSCRIBERS_JSON")
        if subscribers_json:
            data = json.loads(subscribers_json)
        elif not SUBSCRIBERS.exists():
            data = []
        else:
            data = json.loads(SUBSCRIBERS.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{SUBSCRIBERS} must contain a JSON list")
    subscribers = []
    for entry in data:
        if not isinstance(entry, dict) or not isinstance(entry.get("email"), str):
            raise ValueError("Each subscriber must have an email and topics")
        topics = entry.get("topics")
        if not isinstance(topics, list) or not topics or any(not isinstance(topic, str) or not topic.strip() or len(topic) > 160 for topic in topics):
            raise ValueError(f"Subscriber {entry['email']} must have one or more non-empty topics under 160 characters")
        subscribers.append({"email": entry["email"], "topics": list(dict.fromkeys(topic.strip() for topic in topics))})
    if not any(item["email"].lower() == RECIPIENT.lower() for item in subscribers):
        subscribers.append({"email": RECIPIENT, "topics": list(TOPICS.values())})
    return subscribers


def main():
    WORK.mkdir(exist_ok=True)
    previous = json.loads(STATE.read_text()) if STATE.exists() else {"urls": []}
    seen = set(previous.get("urls", []))
    subscribers = load_subscribers()
    topics = list(dict.fromkeys(topic for subscriber in subscribers for topic in subscriber["topics"]))
    if not topics:
        print("No verified subscribers; no email sent.")
        return
    fresh_by_topic = []
    topic_slugs = {}
    for topic in topics:
        slug = hashlib.sha256(topic.casefold().encode("utf-8")).hexdigest()[:12]
        topic_slugs[topic] = slug
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
            fresh_by_topic.append((topic, slug, data, items))

    if not fresh_by_topic:
        print("No new news sources today; no email sent.")
        return

    all_urls = set(seen)
    sections_by_topic = {}
    sources_by_topic = {}
    for topic, slug, data, items in fresh_by_topic:
        summaries = []
        for item in items:
            all_urls.add(item["url"])
        for item in items[:5]:
            url = item["url"]
            title = item.get("title") or url
            snippet = (item.get("content") or item.get("snippet") or "").strip()
            summaries.append(f"[{title}]({url})\n\n{snippet}" if snippet else f"[{title}]({url})")
            sources_by_topic.setdefault(slug, []).append({"title": title, "url": url})
        sections_by_topic[topic] = {"heading": topic, "body": "\n\n".join(summaries)}

    today = date.today().isoformat()
    digest_by_topics = {}
    for subscriber in subscribers:
        selected = [topic for topic in subscriber["topics"] if topic in sections_by_topic]
        if not selected:
            continue
        key = tuple(selected)
        if key not in digest_by_topics:
            sections = [sections_by_topic[slug] for slug in selected]
            labels = selected
            title = " & ".join(labels) + " daily brief"
            newsletter = {
                "subject": f"{' & '.join(labels)} Brief | {today}",
                "preheader": "New developments in " + " and ".join(label.lower() for label in labels) + ", with links to original sources.",
                "title": title,
                "intro": "A source-linked roundup of new developments found in today’s news search.",
                "sections": sections,
                "closing": "Follow the source links for full details and context.",
                "sources": [source for topic in selected for source in sources_by_topic.get(topic_slugs[topic], [])],
                "infographic_prompt": "Create a clear, professional 16:9 newsletter infographic summarizing these developments: " + "; ".join(f"{section['heading']}: {section['body'][:350]}" for section in sections) + ". Use a clean technology editorial style, concise labels, and no invented statistics, unsupported claims, or logos.",
            }
            digest_slug = "_".join(topic_slugs[topic] for topic in selected)
            newsletter_path = WORK / f"auto_newsletter_{digest_slug}.json"
            newsletter_path.write_text(json.dumps(newsletter, ensure_ascii=False, indent=2) + "\n")
            image_path = WORK / f"auto_infographic_{digest_slug}.png"
            run(sys.executable, "tools/generate_infographic.py", "--prompt", newsletter["infographic_prompt"], "--output", str(image_path))
            newsletter["infographic"] = str(image_path.relative_to(ROOT))
            newsletter_path.write_text(json.dumps(newsletter, ensure_ascii=False, indent=2) + "\n")
            html_path = WORK / f"auto_newsletter_{digest_slug}.html"
            run(sys.executable, "tools/render_newsletter.py", str(newsletter_path), "--output", str(html_path))
            digest_by_topics[key] = (newsletter_path, html_path)
        newsletter_path, html_path = digest_by_topics[key]
        run(sys.executable, "tools/send_newsletter.py", str(newsletter_path), "--to", subscriber["email"], "--html", str(html_path), "--confirm-send", "--yes")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"urls": sorted(all_urls), "last_sent": today}, indent=2) + "\n")


if __name__ == "__main__":
    main()
