# Automatic daily web development and AI newsletter

## Schedule and behavior
- Runs every day at 6:00 a.m. Asia/Kolkata on the configured Mac.
- Searches Tavily news from the previous day for web development and AI.
- Sends only when it finds source URLs not previously included in a sent digest.
- Generates a Nano Banana infographic through Kie.ai for each digest that will be sent.
- Sends a personalized digest through Gmail to each address in `.local/subscribers.json`. Subscribers choose `web`, `ai`, or both; each email contains only the selected topic sections. The owner `hs6423590@gmail.com` continues to receive both topics unless listed with custom topics.
- The scheduled job researches the existing Web development and Artificial intelligence topics. Signup choices must use `web` and/or `ai`.
- Stores deduplication state in `.local/newsletter_state.json`; keep this directory between runs.

## Setup requirements
- `.env` must contain working `TAVILY_API_KEY` and `KIE_API_KEY` values.
- `.tmp/token.json` must authorize Gmail with the `gmail.send` scope.
- The project `.venv` must have `requirements.txt` installed.
- Add a subscriber with `.venv/bin/python tools/manage_subscribers.py add person@example.com web ai`; replace the topics with `web`, `ai`, or both. Unsubscribe with `.venv/bin/python tools/manage_subscribers.py remove person@example.com`. The subscriber file is private local data and is not committed.
- The Mac must be running and connected to the network at the scheduled time. A missed run may execute when the Mac wakes.

## Run manually
```sh
.venv/bin/python tools/auto_newsletter.py
```

## Safety and failures
- Never print API keys, OAuth tokens, or credential file contents.
- The workflow updates deduplication state only after Gmail confirms the send.
- Provider, network, or Gmail errors stop the run and are recorded by the scheduler log.
- Only send to addresses explicitly added to the subscriber list or the owner address. New topics require adding a corresponding research topic and signup choice.
