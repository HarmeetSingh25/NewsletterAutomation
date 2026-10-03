#!/usr/bin/env python3
"""Render structured newsletter JSON as email-friendly HTML."""

import argparse
import html
import json
import re
from pathlib import Path


def esc(value):
    return html.escape(str(value or ""), quote=True)


def paragraphs(value):
    blocks = [part.strip() for part in str(value or "").split("\n\n") if part.strip()]
    rendered = []
    for block in blocks:
        safe = esc(block).replace("\n", "<br>")
        safe = re.sub(
            r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
            r'<a href="\2" style="color:#2563eb">\1</a>',
            safe,
        )
        rendered.append(f"<p style=\"margin:0 0 16px;line-height:1.6;color:#334155\">{safe}</p>")
    return "".join(rendered)


def render(newsletter):
    sections = "".join(
        f"<h2 style=\"font-size:20px;color:#0f172a;margin:28px 0 10px\">{esc(section.get('heading'))}</h2>{paragraphs(section.get('body'))}"
        for section in newsletter.get("sections", [])
    )
    image = '<p style="margin:24px 0"><img src="cid:infographic" alt="Newsletter infographic" style="display:block;width:100%;max-width:600px;height:auto;border:0"></p>' if newsletter.get("infographic") else ""
    sources = "".join(
        f'<li style="margin:0 0 8px"><a href="{esc(item.get("url"))}" style="color:#2563eb">{esc(item.get("title") or item.get("url"))}</a></li>'
        for item in newsletter.get("sources", []) if item.get("url")
    )
    sources_section = f'<h2 style="font-size:18px;color:#0f172a;margin:28px 0 10px">Sources</h2><ul style="padding-left:20px;color:#334155">{sources}</ul>' if sources else ""
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(newsletter.get('subject'))}</title></head>
<body style="margin:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif"><div style="display:none;max-height:0;overflow:hidden;opacity:0">{esc(newsletter.get('preheader'))}</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f1f5f9"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="600" cellspacing="0" cellpadding="0" style="width:100%;max-width:600px;background:#fff;border-radius:12px"><tr><td style="padding:36px 32px">
<h1 style="font-size:30px;line-height:1.2;color:#0f172a;margin:0 0 20px">{esc(newsletter.get('title'))}</h1>{paragraphs(newsletter.get('intro'))}{image}{sections}{paragraphs(newsletter.get('closing'))}{sources_section}
</td></tr></table></td></tr></table></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("newsletter", type=Path)
    parser.add_argument("--output", type=Path, default=Path(".tmp/newsletter.html"))
    args = parser.parse_args()
    newsletter = json.loads(args.newsletter.read_text(encoding="utf-8"))
    for required in ("subject", "title", "intro"):
        if not newsletter.get(required):
            parser.error(f"newsletter JSON is missing required field: {required}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(newsletter), encoding="utf-8")
    print(f"Rendered HTML to {args.output}")


if __name__ == "__main__":
    main()
