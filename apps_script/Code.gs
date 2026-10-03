const HEADERS = ["email", "topic", "status", "verify_token", "unsubscribe_token", "created_at"];

function doGet(e) {
  const action = (e && e.parameter && e.parameter.action) || "";
  if (action === "confirm") return actionPage_(confirm_(e.parameter.token));
  if (action === "unsubscribe") return actionPage_(unsubscribe_(e.parameter.token));
  if (action === "subscribers") return subscribersResponse_(e.parameter.key);
  return HtmlService.createHtmlOutputFromFile("signup")
    .setTitle("Subscribe to a topic newsletter")
    .addMetaTag("viewport", "width=device-width, initial-scale=1");
}

function doPost(e) {
  const action = (e && e.parameter && e.parameter.action) || "";
  if (action === "unsubscribe") {
    return ContentService.createTextOutput(unsubscribe_(e.parameter.token).message);
  }
  return ContentService.createTextOutput("Unsupported request");
}

function setupNewsletterSubscribers() {
  const props = PropertiesService.getScriptProperties();
  let sheetId = props.getProperty("SUBSCRIBERS_SHEET_ID");
  let spreadsheet;
  if (sheetId) {
    spreadsheet = SpreadsheetApp.openById(sheetId);
  } else {
    spreadsheet = SpreadsheetApp.create("Newsletter subscribers");
    sheetId = spreadsheet.getId();
    props.setProperty("SUBSCRIBERS_SHEET_ID", sheetId);
    const sheet = spreadsheet.getSheets()[0];
    sheet.setName("Subscribers");
    sheet.appendRow(HEADERS);
  }
  let apiKey = props.getProperty("SUBSCRIBERS_API_KEY");
  if (!apiKey) {
    apiKey = token_() + token_();
    props.setProperty("SUBSCRIBERS_API_KEY", apiKey);
  }
  Logger.log(JSON.stringify({spreadsheetUrl: spreadsheet.getUrl(), subscribersApiKey: apiKey}));
}

function subscribe(emailValue, topicValue, honeypot) {
  const email = String(emailValue || "").trim().toLowerCase();
  const topic = String(topicValue || "").trim().replace(/\s+/g, " ");
  if (honeypot) return {ok: true, message: "If that address can be subscribed, a confirmation email is on its way."};
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return {ok: false, message: "Enter a valid email address."};
  if (!topic || topic.length > 120) return {ok: false, message: "Enter a topic of 1 to 120 characters."};
  const cache = CacheService.getScriptCache();
  const throttleKey = "signup:" + digest_(email);
  if (cache.get(throttleKey)) return {ok: true, message: "If that address can be subscribed, a confirmation email is on its way."};
  if (MailApp.getRemainingDailyQuota() < 1) return {ok: false, message: "Signup confirmations have reached today's limit. Please try again tomorrow."};
  cache.put(throttleKey, "1", 3600);

  const sheet = subscribersSheet_();
  const rows = sheet.getDataRange().getValues();
  for (let i = 1; i < rows.length; i++) {
    if (String(rows[i][0]).toLowerCase() === email && String(rows[i][1]).toLowerCase() === topic.toLowerCase() && rows[i][2] === "confirmed") {
      return {ok: true, message: "That email is already subscribed to this topic."};
    }
  }
  const verifyToken = token_() + token_();
  const unsubscribeToken = token_() + token_();
  const row = rows.findIndex((item, index) => index > 0 && String(item[0]).toLowerCase() === email && String(item[1]).toLowerCase() === topic.toLowerCase());
  const values = [email, topic, "pending", verifyToken, unsubscribeToken, new Date()];
  if (row >= 0) sheet.getRange(row + 1, 1, 1, values.length).setValues([values]);
  else sheet.appendRow(values);

  const base = ScriptApp.getService().getUrl();
  const confirmUrl = base + "?action=confirm&token=" + encodeURIComponent(verifyToken);
  MailApp.sendEmail({
    to: email,
    subject: "Confirm your newsletter subscription",
    body: "Confirm your subscription to " + topic + " by opening this link: " + confirmUrl,
    htmlBody: "<p>Confirm your subscription to <strong>" + escapeHtml_(topic) + "</strong>.</p><p><a href=\"" + confirmUrl + "\">Confirm subscription</a></p><p>If you did not request this, ignore this email.</p>",
  });
  return {ok: true, message: "Check your inbox and confirm the subscription."};
}

function confirm_(token) {
  return changeStatus_(token, "verify", "confirmed", "Subscription confirmed. You will receive this topic's daily newsletter.");
}

function unsubscribe_(token) {
  return changeStatus_(token, "unsubscribe", "unsubscribed", "You have been unsubscribed from this topic.");
}

function changeStatus_(token, tokenKind, status, successMessage) {
  if (!token) return {ok: false, message: "This link is invalid or expired."};
  const sheet = subscribersSheet_();
  const rows = sheet.getDataRange().getValues();
  const tokenColumn = tokenKind === "verify" ? 4 : 5;
  for (let i = 1; i < rows.length; i++) {
    if (rows[i][tokenColumn - 1] === token) {
      sheet.getRange(i + 1, 3).setValue(status);
      if (tokenKind === "verify") sheet.getRange(i + 1, 4).clearContent();
      return {ok: true, message: successMessage};
    }
  }
  return {ok: false, message: "This link is invalid or expired."};
}

function subscribersResponse_(providedKey) {
  const expectedKey = PropertiesService.getScriptProperties().getProperty("SUBSCRIBERS_API_KEY") || "";
  if (!expectedKey || !safeEquals_(String(providedKey || ""), expectedKey)) {
    return ContentService.createTextOutput("Unauthorized").setMimeType(ContentService.MimeType.TEXT);
  }
  const base = ScriptApp.getService().getUrl();
  const rows = subscribersSheet_().getDataRange().getValues();
  const subscribers = [];
  for (let i = 1; i < rows.length; i++) {
    if (rows[i][2] === "confirmed") {
      subscribers.push({
        email: String(rows[i][0]),
        topic: String(rows[i][1]),
        unsubscribe_url: base + "?action=unsubscribe&token=" + encodeURIComponent(String(rows[i][4])),
      });
    }
  }
  return ContentService.createTextOutput(JSON.stringify({subscribers: subscribers})).setMimeType(ContentService.MimeType.JSON);
}

function subscribersSheet_() {
  const id = PropertiesService.getScriptProperties().getProperty("SUBSCRIBERS_SHEET_ID");
  if (!id) throw new Error("Run setupNewsletterSubscribers once before deploying the web app.");
  return SpreadsheetApp.openById(id).getSheetByName("Subscribers");
}

function actionPage_(result) {
  return HtmlService.createHtmlOutput("<!doctype html><html><meta name=\"viewport\" content=\"width=device-width\"><body style=\"font:16px Arial;max-width:560px;margin:48px auto;padding:16px\"><h1>Newsletter subscription</h1><p>" + escapeHtml_(result.message) + "</p></body></html>");
}

function token_() { return Utilities.getUuid().replace(/-/g, ""); }
function digest_(value) { return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, value).map(function (b) { return (b + 256).toString(16).slice(-2); }).join(""); }
function safeEquals_(a, b) { if (a.length !== b.length) return false; let different = 0; for (let i = 0; i < a.length; i++) different |= a.charCodeAt(i) ^ b.charCodeAt(i); return different === 0; }
function escapeHtml_(value) { return String(value).replace(/[&<>\"']/g, function (c) { return ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"})[c]; }); }
