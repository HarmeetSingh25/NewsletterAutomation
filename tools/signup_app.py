#!/usr/bin/env python3
"""Public email signup and verification service for the newsletter."""

import hashlib
import hmac
import base64
import html
import os
import re
import secrets
import sqlite3
import sys
import time
from email.message import EmailMessage
from contextlib import closing
from pathlib import Path
from urllib.parse import urlencode, urljoin

from flask import Flask, abort, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.send_newsletter import gmail_credentials

DATABASE = Path(os.getenv("NEWSLETTER_DB", ROOT / ".local/subscribers.sqlite3"))
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAX_SIGNUP_CONFIRMATIONS_PER_DAY = 50


def connect():
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        db = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        db.execute("""CREATE TABLE IF NOT EXISTS subscribers (
            email TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            verified INTEGER NOT NULL DEFAULT 0,
            verify_hash TEXT,
            verify_expires BIGINT,
            updated_at BIGINT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS signup_attempts (
            ip TEXT NOT NULL,
            created_at BIGINT NOT NULL
        )""")
        db.commit()
        return db
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS subscribers (
        email TEXT PRIMARY KEY COLLATE NOCASE,
        topic TEXT NOT NULL,
        verified INTEGER NOT NULL DEFAULT 0,
        verify_hash TEXT,
        verify_expires INTEGER,
        updated_at INTEGER NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS signup_attempts (
        ip TEXT NOT NULL,
        created_at INTEGER NOT NULL
    )""")
    db.commit()
    return db


def execute(db, query, params=()):
    if DATABASE_URL:
        query = query.replace("?", "%s")
    return db.execute(query, params)


def send_verification(email, token):
    base_url = os.environ["PUBLIC_SIGNUP_URL"].rstrip("/")
    link = urljoin(base_url + "/", "verify/" + token)
    message = EmailMessage()
    message["To"] = email
    message["Subject"] = "Confirm your newsletter signup"
    message.set_content(f"Confirm your email and topic subscription by opening this link:\n\n{link}\n\nThis link expires in 24 hours. If you did not request this, ignore this message.")
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    build("gmail", "v1", credentials=gmail_credentials()).users().messages().send(userId="me", body={"raw": raw}).execute()


@app.get("/")
def signup_form():
    return """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Newsletter signup</title>
<body style="font:16px system-ui;max-width:620px;margin:48px auto;padding:0 20px;color:#172033"><h1>Get a newsletter about your topic</h1><p>Enter your email and a topic. After you confirm, you’ll receive a daily email when there is new reporting about that topic. You can unsubscribe at any time.</p>
<form method="post" action="/signup"><label>Email<br><input required type="email" name="email" autocomplete="email" maxlength="254" style="width:100%;padding:12px;margin:8px 0 18px;box-sizing:border-box"></label><label>What topic should we follow?<br><input required name="topic" maxlength="160" placeholder="e.g. climate technology" style="width:100%;padding:12px;margin:8px 0 18px;box-sizing:border-box"></label><button style="padding:12px 20px">Send verification email</button></form></body></html>"""


@app.post("/signup")
def signup():
    email = request.form.get("email", "").strip().lower()
    topic = " ".join(request.form.get("topic", "").split())
    if not EMAIL_RE.fullmatch(email) or len(email) > 254 or not topic or len(topic) > 160:
        abort(400, "Enter a valid email and a topic under 160 characters.")
    now = int(time.time())
    ip = request.remote_addr or "unknown"
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with closing(connect()) as db, db:
        execute(db, "DELETE FROM signup_attempts WHERE created_at < ?", (now - 86400,))
        daily_attempts = execute(db, "SELECT COUNT(*) AS count FROM signup_attempts").fetchone()["count"]
        if daily_attempts >= MAX_SIGNUP_CONFIRMATIONS_PER_DAY:
            abort(429, "Signup confirmations have reached today's limit. Try again tomorrow.")
        attempts = execute(db, "SELECT COUNT(*) AS count FROM signup_attempts WHERE ip = ?", (ip,)).fetchone()["count"]
        if attempts >= 10:
            abort(429, "Too many signup requests. Try again tomorrow.")
        execute(db, "INSERT INTO signup_attempts(ip, created_at) VALUES (?, ?)", (ip, now))
        execute(db, """INSERT INTO subscribers(email, topic, verified, verify_hash, verify_expires, updated_at)
            VALUES (?, ?, 0, ?, ?, ?) ON CONFLICT(email) DO UPDATE SET topic=excluded.topic,
            verified=0, verify_hash=excluded.verify_hash, verify_expires=excluded.verify_expires,
            updated_at=excluded.updated_at""", (email, topic, token_hash, now + 86400, now))
    send_verification(email, token)
    return "Check your inbox for a verification link. Your subscription starts after you confirm your email.", 202


@app.get("/verify/<token>")
def verify(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = int(time.time())
    with closing(connect()) as db, db:
        row = execute(db, "SELECT email FROM subscribers WHERE verify_hash=? AND verify_expires>=?", (token_hash, now)).fetchone()
        if row is None:
            abort(400, "This verification link is invalid or expired. Please sign up again.")
        execute(db, "UPDATE subscribers SET verified=1, verify_hash=NULL, verify_expires=NULL, updated_at=? WHERE email=?", (now, row["email"]))
    return "Your email is verified. You’re subscribed to the requested topic."


def unsubscribe_signature(email):
    key = os.getenv("UNSUBSCRIBE_SIGNING_KEY", "")
    if len(key) < 32:
        raise RuntimeError("UNSUBSCRIBE_SIGNING_KEY must be configured with at least 32 characters")
    return hmac.new(key.encode(), email.lower().encode(), hashlib.sha256).hexdigest()


@app.route("/unsubscribe", methods=["GET", "POST"])
def unsubscribe():
    email = request.values.get("email", "").strip().lower()
    supplied = request.values.get("sig", "")
    if not EMAIL_RE.fullmatch(email):
        abort(400, "This unsubscribe link is invalid.")
    try:
        expected = unsubscribe_signature(email)
    except RuntimeError:
        abort(503, "Unsubscribe is temporarily unavailable.")
    if not hmac.compare_digest(supplied, expected):
        abort(400, "This unsubscribe link is invalid.")
    if request.method == "GET":
        safe_email = html.escape(email, quote=True)
        safe_signature = html.escape(supplied, quote=True)
        return ("<!doctype html><html><meta name='viewport' content='width=device-width'>"
                "<body style='font:16px system-ui;max-width:560px;margin:48px auto;padding:16px'>"
                "<h1>Unsubscribe</h1><p>Confirm that you want to stop topic newsletters at this address.</p>"
                "<form method='post' action='/unsubscribe'>"
                f"<input type='hidden' name='email' value='{safe_email}'>"
                f"<input type='hidden' name='sig' value='{safe_signature}'>"
                "<button type='submit'>Unsubscribe</button></form></body></html>")
    now = int(time.time())
    with closing(connect()) as db, db:
        execute(db, "UPDATE subscribers SET verified=0, verify_hash=NULL, verify_expires=NULL, updated_at=? WHERE email=?", (now, email))
    return "You are unsubscribed. You will not receive further topic newsletters."


@app.get("/api/subscribers")
def api_subscribers():
    expected = os.getenv("SUBSCRIBER_API_TOKEN", "")
    supplied = request.headers.get("Authorization", "")
    if not expected or not hmac.compare_digest(supplied, "Bearer " + expected):
        abort(401)
    try:
        signing_key = os.getenv("UNSUBSCRIBE_SIGNING_KEY", "")
        if len(signing_key) < 32:
            raise RuntimeError("Unsubscribe signing key is not configured")
        public_url = os.environ["PUBLIC_SIGNUP_URL"].rstrip("/")
    except (KeyError, RuntimeError):
        abort(503, "Subscriber API is not fully configured.")
    with closing(connect()) as db, db:
        rows = execute(db, "SELECT email, topic FROM subscribers WHERE verified=1 ORDER BY email").fetchall()
    result = []
    for row in rows:
        email = row["email"]
        query = urlencode({"email": email, "sig": unsubscribe_signature(email)})
        result.append({"email": email, "topics": [row["topic"]], "unsubscribe_url": public_url + "/unsubscribe?" + query})
    return jsonify(result)


if __name__ == "__main__":
    if not os.getenv("PUBLIC_SIGNUP_URL") or not os.getenv("SUBSCRIBER_API_TOKEN"):
        raise SystemExit("Set PUBLIC_SIGNUP_URL and SUBSCRIBER_API_TOKEN before starting the signup service.")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
