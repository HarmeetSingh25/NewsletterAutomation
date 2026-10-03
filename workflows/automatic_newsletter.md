# Automatic daily newsletter

## Schedule and behavior
- GitHub Actions runs every day at 6:00 a.m. Asia/Kolkata.
- Searches Tavily news from the previous day for each distinct topic requested by a verified subscriber.
- Sends only when it finds source URLs not previously included in a sent digest.
- Generates a Nano Banana infographic through Kie.ai for each digest that will be sent.
- Sends personalized, topic-matched digests through Gmail. The owner `hs6423590@gmail.com` continues to receive Web development and Artificial intelligence topics.
- Stores deduplication state in `.local/newsletter_state.json`; keep this directory between runs.

## Signup service setup
- Deploy `tools/signup_app.py` as a persistent web service using the root `Procfile`.
- Configure `PUBLIC_SIGNUP_URL`, `SUBSCRIBER_API_TOKEN`, `GMAIL_TOKEN_JSON`, and `NEWSLETTER_DB` on the hosting service. Mount persistent storage for `NEWSLETTER_DB` so verified subscriptions survive restarts. The Gmail token must have the `gmail.send` scope.
- Add GitHub Actions repository secrets `NEWSLETTER_SIGNUP_API_URL` (the deployed public origin) and `SUBSCRIBER_API_TOKEN` (the same secret as on the web service). The workflow fetches only verified subscribers through the authenticated API.
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
- The workflow updates deduplication state only after Gmail confirms all sends.
- Provider, network, or Gmail errors stop the run and are recorded by the scheduler log.
- The signup API exposes subscriber data only with the bearer token and returns verified email addresses only.
