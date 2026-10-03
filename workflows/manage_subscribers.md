# Public topic newsletter signup

The public signup page is a Google Apps Script web app. Subscribers enter an email and a free-form topic. The service sends a confirmation link, keeps pending addresses out of the newsletter, and gives each confirmed topic subscription its own unsubscribe link. The GitHub Actions job searches each distinct topic and sends only to confirmed subscriptions.

## Deploy the signup app

1. Open [Google Apps Script](https://script.google.com/) and create a new project.
2. Add the contents of `apps_script/Code.gs` to `Code.gs`. Add an HTML file named `signup` and paste `apps_script/signup.html` into it.
3. Save, select `setupNewsletterSubscribers`, and click **Run**. Approve the requested Google Sheets and email permissions. In the execution log, copy the `spreadsheetUrl` and `subscribersApiKey`; keep the key private.
4. Choose **Deploy → New deployment → Web app**. Set **Execute as** to yourself and access to **Anyone**. Deploy and copy the web app URL ending in `/exec`.
5. In the GitHub repository, open **Settings → Secrets and variables → Actions** and add:
   - `NEWSLETTER_SIGNUP_API_URL`: the web app `/exec` URL.
   - `SUBSCRIBER_API_TOKEN`: the `subscribersApiKey` from the setup run.
6. Share the web app URL as the signup page. Subscribers must confirm from email before they receive topic newsletters.

The spreadsheet is created in the deploying Google account and is not shared with signups. The public app limits repeated confirmation requests for the same email and uses a hidden form field to deter simple bots. Apps Script currently limits personal Gmail accounts to 100 MailApp recipients per day for signup confirmations. The newsletter runner caps its sends at 400 recipient/topic messages per day to leave room under Gmail's personal account sending limit.

## Manage subscriptions

- The sheet is named `Newsletter subscribers`; change a row's status to `unsubscribed` to remove a subscription manually.
- Each newsletter contains an unsubscribe link and one-click unsubscribe headers.
- If the web app is redeployed with a new URL, update the `NEWSLETTER_SIGNUP_API_URL` Actions secret.
- The scheduled sender still adds `hs6423590@gmail.com` to the Web development and Artificial intelligence topics for the owner.
