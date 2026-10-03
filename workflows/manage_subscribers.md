# Host the public topic signup page

The Flask app in `tools/signup_app.py` serves the public signup page, verifies email addresses, stores subscribers in PostgreSQL, and provides a protected subscriber API to the GitHub Actions sender. New subscribers are not mailed until they confirm. Newsletter messages include a body unsubscribe link and one-click unsubscribe headers.

## Deploy the signup app

1. Import this GitHub repository into a Vercel project. Vercel detects the Flask `app` exported from root `app.py`.
2. Attach a PostgreSQL database and configure `DATABASE_URL` (or `POSTGRES_URL`) in the Vercel production environment.
3. Configure these Vercel production environment variables:
   - `GMAIL_TOKEN_JSON`: the contents of `.tmp/token.json`.
   - `SUBSCRIBER_API_TOKEN`: a long random secret; use the same value in GitHub Actions.
   - `UNSUBSCRIBE_SIGNING_KEY`: a separate random secret at least 32 characters long.
4. Deploy once to get the production URL. Set `PUBLIC_SIGNUP_URL` to that HTTPS URL in Vercel, then redeploy.
5. In the GitHub repository’s **Settings → Secrets and variables → Actions**, set:
   - `NEWSLETTER_SIGNUP_API_URL`: `https://YOUR-PRODUCTION-DOMAIN/api/subscribers`.
   - `SUBSCRIBER_API_TOKEN`: the same secret configured in Vercel.
6. Share the production root URL as the signup page.

Keep the Gmail token and both random keys private. Do not commit them or paste them into chat. The signup database must be persistent PostgreSQL; Vercel's function filesystem is not suitable for keeping subscriber records. Vercel supports root `app.py` Flask deployments with zero configuration; see [Vercel's Flask deployment guide](https://vercel.com/docs/frameworks/backend/flask).

The current Gmail account can send up to 500 messages per day. Signup is limited to 50 confirmation messages per day and 10 requests per IP per day; the scheduled sender caps newsletters at 400 email/topic messages to leave room for confirmations. If the list grows, move newsletter delivery to a dedicated mailing provider. Google also requires subscribed/marketing mail to provide an unsubscribe mechanism; this app provides a confirmation page for link clicks and supports one-click unsubscribe POST requests.

Vercel skips deployments when a commit changes only `.local/newsletter_state.json`, so daily deduplication commits do not redeploy the signup app.
