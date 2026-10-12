# Google sign-in and account email setup

Use personal accounts for SearchScribe. Do not use office OAuth projects, mailbox credentials, or DNS.

## Current status

The deployed password flow was verified on https://searchscribe-ai.vercel.app on 7 October 2026: signup/login, real Gemini generation, article and SEO edits, version restore, HTML download, refresh, logout, and cross-user access denial. Google sign-in was merged in PR #10 and deployed. The existing personal account signed in with Google and recovered its saved articles on 9 October. A separate password test account received its verification email and completed verification that day. Branded security emails shipped in PR #16; the opaque email-logo fix shipped in PR #17. A fresh password-to-Google linking journey, actual mobile rendering of the new logo, and the complete live password-reset journey remain acceptance gates.

## Google Cloud: line by line

1. Open the personal **SearchScribe AI** project (`searchscribe-ai`) in Google Cloud. No billing account is required for this sign-in setup.
2. Open **Google Auth Platform → Branding** (or **Get started**).
3. App name: **SearchScribe AI**.
4. User support email: choose the personal support mailbox you authorize. This address may appear on the consent screen.
5. Audience: **External**. Begin in testing while validating the integration.
6. Developer contact email: your authorized personal contact mailbox.
7. Read Google's policy acknowledgement and complete it yourself if consent is requested.
8. Branding: homepage `https://searchscribe-ai.vercel.app`; privacy policy `https://searchscribe-ai.vercel.app/privacy`. Do not invent a terms URL. Add one when actual terms have been written.
9. Open **Clients → Create client → Web application**. Name: **SearchScribe web**.
10. Authorized JavaScript origins, one per row, with no paths or trailing slash:
    - `https://searchscribe-ai.vercel.app`
    - `http://localhost:3100` (only if this remains your development port)
11. This implementation uses the GIS popup JavaScript callback, not an authorization-code redirect. Leave authorized redirect URIs empty. Do not paste the Render API URL as a JavaScript origin.
12. Use only basic identity scopes (openid/email/profile). Do not request Gmail, Drive, Calendar, or offline access.
13. Copy the **client ID** ending in `.apps.googleusercontent.com`. This is public configuration. This flow does not use the client secret; do not share or commit it.
14. Render **searchscribe-beta-api → Environment**: add `GOOGLE_CLIENT_ID=<your web client ID>`. Save and deploy the reviewed backend commit. Keep `CORS_ORIGINS=https://searchscribe-ai.vercel.app`.
15. The frontend obtains the client ID and a five-minute nonce challenge from `/api/v1/auth/google/challenge`. No frontend Google secret or `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is needed. Preview deployments must use an isolated backend; do not point every preview at production data.
16. Test: new Google identity creates an account; refresh survives page reload; logout ends the session. A matching password-account email must show linking instructions, never silently merge.
17. Existing password user: login → **Account** → confirm password → Google button → choose the same email. Confirm both methods reach the same articles.
18. Check Audience's test-user restrictions, publishing status, and Verification Center before opening Google login to everyone. Follow the console's requirements; testing success is not proof of public availability.

Official references: [GIS setup](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid), [server token verification](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).

## Email without an owned domain

The `vercel.app` address hosts the website; you cannot configure its DNS as your own sending domain. Resend's `onboarding@resend.dev` sender is restricted to the account owner's email and cannot send password resets to arbitrary public users. Do not present a test sender as production email.

For this Render Free API, use an **HTTPS transactional email API**, not Gmail SMTP. Render Free blocks outbound SMTP ports 25, 465, and 587. A Gmail App Password cannot fix that hosting restriction.

Brevo Free is a candidate for the zero-spend beta: its documented limit is 300 email sends per day. With a free mailbox sender or an unauthenticated domain, Brevo temporarily replaces the sender address with a compliant one. This affects branding and must be tested before public recovery is enabled. Account approval and transactional sending availability must be checked; do not claim guaranteed delivery or unlimited capacity.

### Brevo preparation: line by line

1. Open [Brevo](https://www.brevo.com/) and create a separate personal account using the authorized support email. The user must approve/accept any terms and complete verification challenges. Do not create an office account or enter a payment card.
2. Choose **Free**. Confirm the dashboard shows no paid subscription or add-on.
3. Complete account email verification and any required sender/account activation. Do not fabricate business details.
4. Open **Settings → Senders, Domains & Dedicated IPs → Senders → Add a sender** (labels may vary).
5. Sender name: **SearchScribe AI**. Sender email: the authorized personal support mailbox. Complete the verification email yourself. Without an owned domain, do not try to authenticate gmail.com or vercel.app.
6. Open **Transactional → Settings** and confirm transactional sending is activated for this account. Check the provider's effective sender rewrite and delivery rules.
7. Open **SMTP & API → API Keys**. Create a dedicated key named **SearchScribe Render transactional**. Use an API key, not an SMTP password. Key creation requires explicit approval because it grants sending access.
8. Enter the key directly into **searchscribe-beta-api → Environment** as a secret. Never paste it in chat or commit it.
9. The recovery/email PR should implement these settings:

   | Setting                        | Value                                      |
   | ------------------------------ | ------------------------------------------ |
   | `MAIL_PROVIDER`                | `brevo`                                    |
   | `BREVO_API_KEY`                | dedicated key, Render secret only          |
   | `MAIL_FROM_EMAIL`              | verified personal support mailbox          |
   | `MAIL_FROM_NAME`               | `SearchScribe AI`                          |
   | `PUBLIC_SITE_URL`              | `https://searchscribe-ai.vercel.app`       |
   | `SECURITY_EMAIL_LINKS_ENABLED` | `false` until untracked links are verified |

The recovery implementation reads these variables. The send integration uses HTTPS `POST https://api.brevo.com/v3/smtp/email` with a bounded timeout, no redirects and no automatic retry: an ambiguous timeout may already have sent the message. Apply the recovery migration and deploy the reviewed recovery commit before enabling the flow. No mail credentials belong in Vercel's browser configuration.

10. In **Settings → Contacts → Per-contact pixel tracking consent**, enable **Yes** and set **Track contacts whose consent is unknown** to **No**. This changes existing contacts to Unknown; use only the personal account. The integration sends `contactPixelTrackingConsent: false` on each recipient. Before setting `SECURITY_EMAIL_LINKS_ENABLED=true`, verify a fresh delivered security message has direct canonical links, intact fragments, and no Brevo open-tracking pixel. Anonymized tracking alone is not tracking disabled. Never copy a live security token into logs, screenshots, or chat.
11. Test with addresses whose owners authorize the messages. Verify the actual inbox, spam folder, visible sender rewrite, plain-text fallback, expiry, and password-change notice. Opening a verification link must not consume it; only explicit confirmation sends the POST. A reset link opens the new-password form and must not change the password until submission. Provider acceptance alone does not establish delivery.
12. Keep a persistent daily send cap below the provider's free limit, with a reserve for password resets. Never send marketing without consent. Later move to a verified owned sender domain without changing the public app URL.

References: [Render Free SMTP restriction](https://render.com/docs/free), [Brevo sender compliance and temporary replacement](https://help.brevo.com/hc/en-us/articles/14925263522578-Comply-with-Gmail-Yahoo-and-Microsoft-s-requirements-for-email-senders), [Brevo Free limits](https://help.brevo.com/hc/en-us/articles/208589409-About-Brevo-s-pricing-plans), [transactional email API](https://developers.brevo.com/reference/sendtransacemail).

## Recovery/email implementation acceptance

- Login includes **Forgot password?**; request screen always returns the same neutral message for known and unknown emails.
- Generate cryptographically random reset codes; store only their hashes in Postgres with expiry and atomic single-use consumption. Defaults: 30-minute reset expiry, 24-hour verification expiry, 3 security-email requests per email/hour and 20 per ASGI client IP/hour.
- Send branded HTML plus plain text. With security links enabled, the canonical verify/reset URL carries the opaque token in its fragment; the form immediately removes it from the address bar, retains it only in memory, and submits it in a POST body after the user's action. No token belongs in a query string, analytics, browser storage, or logs. Expiry and atomic single-use checks remain server-side. The disabled default preserves manual-code emails; old-email code entry remains available in the forms. Brevo's per-recipient tracking flag requires account activation and an actual delivered-message check; see [official tracking-consent guidance](https://help.brevo.com/hc/en-us/articles/37114679474706-About-email-tracking-pixels-and-the-CNIL-recommendation-in-Brevo).
- New-password validation matches signup. Consume tokens atomically, invalidate all sessions (including access tokens), and send a password-change notice. Do not automatically log the user in after reset.
- A Google-only account remains Google-only; a reset request must not silently turn it into a password account. Explain the appropriate sign-in route without exposing account existence.
- Add email verification for password accounts with expiring, hashed, single-use tokens; resend limits; delivery failure handling. Google verified identity can satisfy Google-account email verification, but never authorize merging by email alone.
- Welcome mail is optional and separate from marketing consent. Do not enroll users into newsletters by default.
- Prove expiration, replay rejection, concurrency, unknown-email neutrality, rate limits, session revocation, and no cross-user access. Prove deployed inbox delivery before claiming recovery is ready.

## Operational boundaries

The persistent daily send cap defaults to 250 across all security messages, with
50 reserved from verification traffic for recovery and change notices. Provider
failures still spend a reservation. Network delivery runs after the response and
database commit; signup succeeds even when delivery fails. A process crash before
the background send can lose that message, so the UI supports a bounded resend.
This beta does not yet use a durable delivery queue.

Rate limiting trusts the ASGI client address and ignores raw forwarding headers.
Vercel proxy traffic may share an IP budget; verify effective proxy behavior before
increasing public capacity. Do not trust arbitrary `X-Forwarded-For` values to
solve this. Password reset increments the account session version and revokes
refresh sessions, so old access tokens also stop working. Existing accounts keep
their articles and Google links; advisory verification does not lock out legacy
password users.
