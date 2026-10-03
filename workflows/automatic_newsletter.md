# Automatic daily newsletter

## Schedule and behavior
- GitHub Actions runs every day at 6:00 a.m. Asia/Kolkata.
- Searches Tavily news from the previous day for each distinct topic requested by a verified subscriber.
- Sends only when it finds source URLs not previously included in a sent digest.
- Generates a Nano Banana infographic through Kie.ai for each digest that will be sent.
- Sends personalized, topic-matched digests through Gmail. The owner `hs6423590@gmail.com` continues to receive Web development and Artificial intelligence topics.
- Stores deduplication state in `.local/newsletter_state.json`; keep this directory between runs.

## Signup service setup
- Import this repository as a Vercel project. Vercel detects the Flask app through the root `app.py` entry point.
- Add a Postgres database through Vercel Marketplace and make its connection string available as `DATABASE_URL`. Subscriber records are stored in Postgres because Vercel function filesystems are not persistent.
- Configure `PUBLIC_SIGNUP_URL`, `SUBSCRIBER_API_TOKEN`, and `GMAIL_TOKEN_JSON` in Vercel. The Gmail token must have the `gmail.send` scope. `PUBLIC_SIGNUP_URL` must be the deployed HTTPS origin.
- Add GitHub Actions repository secrets `NEWSLETTER_SIGNUP_API_URL` (the deployed URL ending in `/api/subscribers`) and `SUBSCRIBER_API_TOKEN` (the same secret as on the web service). Also set `UNSUBSCRIBE_SIGNING_KEY` in Vercel so the API can attach signed unsubscribe links to each address.
- Open the deployed service root to sign up with an email and freeform topic. The service sends a Gmail verification link; the address receives newsletters only after the link is opened.
- `NEWSLETTER_SUBSCRIBERS_JSON` remains an optional manual fallback when `NEWSLETTER_SIGNUP_API_URL` is unset.

## Newsletter job requirements
- GitHub Actions secrets `TAVILY_API_KEY`, `KIE_API_KEY`, and `GMAIL_TOKEN_JSON` must be configured.
- The project dependencies in `requirements.txt` must be installed.

## Run manually
```sh
.venv/bin/python tools/auto_newsletter.py
```

## Safety and failures
- Never print API keys, OAuth tokens, or credential file contents.
- The workflow updates per-subscriber deduplication state after each Gmail send succeeds.
- Provider, network, or Gmail errors stop the run and are recorded by the scheduler log.
- The signup API exposes subscriber data only with the bearer token and returns verified email addresses only.
