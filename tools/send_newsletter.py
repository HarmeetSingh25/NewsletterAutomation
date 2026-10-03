#!/usr/bin/env python3
"""Send a reviewed newsletter using Gmail after explicit CLI confirmation."""

import argparse
import base64
import json
import mimetypes
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[1]
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def gmail_credentials():
    credential_candidates = (
        ROOT / "credentials.json",
        ROOT / ".tmp/credentials.json",
        *sorted((ROOT / ".tmp").glob("client_secret_*.json")),
    )

    def is_oauth_client(path):
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return isinstance(config, dict) and any(
            isinstance(config.get(kind), dict) for kind in ("installed", "web")
        )

    credentials = next((path for path in credential_candidates if path.exists() and is_oauth_client(path)), None)
    if credentials is None:
        raise FileNotFoundError("Add a Google Desktop OAuth client as credentials.json in the project root or .tmp/")
    token = credentials.parent / "token.json"
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials), SCOPES)
            creds = flow.run_local_server(port=0)
        token.write_text(creds.to_json(), encoding="utf-8")
    return creds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("newsletter", type=Path)
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--html", type=Path, default=ROOT / ".tmp/newsletter.html")
    parser.add_argument("--confirm-send", action="store_true", help="Require interactive confirmation before sending")
    args = parser.parse_args()
    if not args.confirm_send:
        parser.error("sending requires --confirm-send")
    newsletter = json.loads(args.newsletter.read_text(encoding="utf-8"))
    html_path = args.html.resolve()
    if not html_path.exists():
        parser.error(f"HTML preview not found: {html_path}")
    message = EmailMessage()
    message["To"] = args.to
    message["Subject"] = newsletter["subject"]
    message.set_content(f"{newsletter.get('title', newsletter['subject'])}\n\nOpen this email in an HTML-capable mail client to view the formatted newsletter.")
    message.add_alternative(html_path.read_text(encoding="utf-8"), subtype="html")
    image_path = newsletter.get("infographic")
    if image_path:
        path = Path(image_path)
        if not path.is_absolute():
            path = ROOT / path
        if path.exists():
            mime_type, _ = mimetypes.guess_type(path.name)
            maintype, subtype = (mime_type or "image/png").split("/", 1)
            message.get_payload()[-1].add_related(path.read_bytes(), maintype=maintype, subtype=subtype, cid="<infographic>", filename=path.name)
    print(f"To: {args.to}\nSubject: {newsletter['subject']}\nHTML preview: {html_path}")
    if input("Type SEND to deliver this email: ").strip() != "SEND":
        print("Cancelled; no email sent.")
        return
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    result = build("gmail", "v1", credentials=gmail_credentials()).users().messages().send(userId="me", body={"raw": encoded}).execute()
    print(f"Sent. Gmail message ID: {result.get('id')}")


if __name__ == "__main__":
    main()
