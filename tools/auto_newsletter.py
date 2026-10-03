#!/usr/bin/env python3
"""Build topic-specific newsletters for confirmed subscribers and send them through Gmail."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".local/newsletter_state.json"
WORK = ROOT / ".tmp"
RECIPIENT = "hs6423590@gmail.com"
OWNER_TOPICS = ("Web development", "Artificial intelligence")
MAX_MESSAGES_PER_RUN = 400
MAX_TOPICS_PER_RUN = 20


def canonical_url(value):
    parts = urlsplit(value)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def topic_key(topic):
    return " ".join(topic.casefold().split())


def subscriber_key(email, topic):
    return hashlib.sha256((email.strip().lower() + "\0" + topic_key(topic)).encode("utf-8")).hexdigest()


def load_subscribers():
    api_url = os.getenv("NEWSLETTER_SIGNUP_API_URL", "").strip()
    api_token = os.getenv("SUBSCRIBER_API_TOKEN", "").strip()
    if api_url:
        if not api_token:
            raise ValueError("SUBSCRIBER_API_TOKEN is required with NEWSLETTER_SIGNUP_API_URL")
        query = urlencode({"action": "subscribers", "key": api_token})
        request = Request(api_url + ("&" if "?" in api_url else "?") + query)
        with urlopen(request, timeout=60) as response:
            data = json.load(response)
        if isinstance(data, dict):
            data = data.get("subscribers")
    else:
        raw = os.getenv("NEWSLETTER_SUBSCRIBERS_JSON", "").strip()
        data = json.loads(raw) if raw else []

    if not isinstance(data, list):
        raise ValueError("The subscriber service must return a JSON list")
    subscribers = []
    unique = set()
    for entry in data:
        if not isinstance(entry, dict) or not isinstance(entry.get("email"), str):
            raise ValueError("Each subscriber record must contain an email address")
        email = entry["email"].strip()
        one_topic = entry.get("topic")
        topics = [one_topic] if isinstance(one_topic, str) else entry.get("topics", [])
        if not email or not isinstance(topics, list) or not topics:
            raise ValueError("Each subscriber record must contain an email address and at least one topic")
        for topic in topics:
            if not isinstance(topic, str) or not topic.strip() or len(topic.strip()) > 120:
                raise ValueError("Subscriber topics must contain 1 to 120 characters")
            topic = " ".join(topic.strip().split())
            pair = (email.lower(), topic_key(topic))
            if pair in unique:
                continue
            unique.add(pair)
            unsubscribe_url = entry.get("unsubscribe_url")
            if not unsubscribe_url and isinstance(entry.get("unsubscribe_urls"), dict):
                unsubscribe_url = entry["unsubscribe_urls"].get(topic)
            subscribers.append({"email": email, "topic": topic, "unsubscribe_url": unsubscribe_url or ""})

    for topic in OWNER_TOPICS:
        pair = (RECIPIENT.lower(), topic_key(topic))
        if pair not in unique:
            subscribers.append({"email": RECIPIENT, "topic": topic, "unsubscribe_url": ""})
            unique.add(pair)
    if len(subscribers) > MAX_MESSAGES_PER_RUN:
        raise ValueError(f"There are more than {MAX_MESSAGES_PER_RUN} email/topic subscriptions; no emails were sent")
    distinct_topics = {topic_key(item["topic"]) for item in subscribers}
    if len(distinct_topics) > MAX_TOPICS_PER_RUN:
        raise ValueError(f"There are more than {MAX_TOPICS_PER_RUN} distinct topics; no emails were sent")
    return subscribers


def write_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(STATE)


def source_text(item):
    title = item.get("title") or item["url"]
    snippet = (item.get("content") or item.get("snippet") or "").strip()
    return f"[{title}]({item['url']})\n\n{snippet}" if snippet else f"[{title}]({item['url']})"


def main():
    WORK.mkdir(exist_ok=True)
    previous = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    sent = previous.get("sent", {})
    legacy_urls = set(previous.get("urls", []))
    subscribers = load_subscribers()
    grouped = {}
    for subscriber in subscribers:
        grouped.setdefault(topic_key(subscriber["topic"]), []).append(subscriber)

    today = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
    sent_messages = 0
    for normalized_topic, members in grouped.items():
        topic = members[0]["topic"]
        topic_slug = hashlib.sha256(normalized_topic.encode("utf-8")).hexdigest()[:12]
        research_path = WORK / f"auto_research_{topic_slug}.json"
        run(
            sys.executable, "tools/research_topic.py", topic,
            "--topic-type", "news", "--time-range", "day", "--limit", "10",
            "--output", str(research_path),
        )
        research = json.loads(research_path.read_text(encoding="utf-8"))
        items = []
        for item in research.get("results", []):
            if item.get("url"):
                item["url"] = canonical_url(item["url"])
                items.append(item)
        if not items:
            continue

        per_subscriber = {}
        image_items = {}
        for subscriber in members:
            key = subscriber_key(subscriber["email"], subscriber["topic"])
            seen = set(sent.get(key, []))
            if not seen and subscriber["email"].lower() == RECIPIENT.lower() and topic in OWNER_TOPICS:
                seen.update(legacy_urls)
            fresh = [item for item in items if item["url"] not in seen]
            if fresh:
                per_subscriber[key] = (subscriber, fresh, seen)
                for item in fresh:
                    image_items[item["url"]] = item
        if not per_subscriber:
            continue

        union_items = list(image_items.values())[:10]
        image_prompt = (
            f"Create a concise, accurate 16:9 email infographic about {topic}. "
            "Use only these source headlines and summaries: "
            + "; ".join(source_text(item)[:300] for item in union_items)
            + ". Use a polished technology editorial style, readable short labels, and no invented facts or statistics."
        )
        image_base = WORK / f"auto_infographic_{topic_slug}.png"
        run(sys.executable, "tools/generate_infographic.py", "--prompt", image_prompt, "--output", str(image_base))
        image_path = max(WORK.glob(f"auto_infographic_{topic_slug}.*"), key=lambda path: path.stat().st_mtime)

        for key, (subscriber, fresh, seen) in per_subscriber.items():
            newsletter = {
                "subject": f"{topic} Brief | {today}",
                "preheader": f"New developments about {topic}, with links to original sources.",
                "title": f"{topic}: daily brief",
                "intro": f"A source-linked roundup of new developments about {topic} found today.",
                "sections": [{"heading": topic, "body": "\n\n".join(source_text(item) for item in fresh[:5])}],
                "closing": "Follow the source links for full details and context.",
                "sources": [{"title": item.get("title") or item["url"], "url": item["url"]} for item in fresh[:5]],
                "infographic": str(image_path.relative_to(ROOT)),
                "unsubscribe_url": subscriber["unsubscribe_url"],
            }
            newsletter_slug = key[:12]
            newsletter_path = WORK / f"auto_newsletter_{topic_slug}_{newsletter_slug}.json"
            html_path = WORK / f"auto_newsletter_{topic_slug}_{newsletter_slug}.html"
            newsletter_path.write_text(json.dumps(newsletter, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            run(sys.executable, "tools/render_newsletter.py", str(newsletter_path), "--output", str(html_path))
            command = [
                sys.executable, "tools/send_newsletter.py", str(newsletter_path),
                "--to", subscriber["email"], "--html", str(html_path), "--confirm-send", "--yes", "--redact-recipient",
            ]
            if subscriber["unsubscribe_url"]:
                command.extend(["--unsubscribe-url", subscriber["unsubscribe_url"]])
            run(*command)
            sent[key] = sorted(seen | {item["url"] for item in fresh})
            write_state({"sent": sent, "urls": sorted(legacy_urls), "last_sent": today})
            sent_messages += 1

    print(f"Sent {sent_messages} topic newsletter(s) to confirmed subscribers.")


if __name__ == "__main__":
    main()
