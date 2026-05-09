# macmini-watch

Watches Apple's [refurbished Mac mini page](https://www.apple.com/shop/refurbished/mac/mac-mini)
and pings a Discord channel when an M4 Mac mini drops at or below your price cap.

Runs free on GitHub Actions every ~10 minutes. No dependencies, ~150 lines of Python.

## Setup (5 minutes)

### 1. Fork or create this repo

Easiest: click **Use this template** or create a new public repo and drop in `check.py`,
`.github/workflows/check.yml`, and an empty `seen.json` (`echo "[]" > seen.json`).

Public repos get unlimited free Actions minutes; private repos get 2,000/month.

### 2. Make a Discord webhook

In Discord: pick a server you own → **Server Settings → Integrations → Webhooks → New Webhook**.
Choose a channel, hit **Copy Webhook URL**. It looks like
`https://discord.com/api/webhooks/12345.../abc...`.

If you don't have a server, make one (free, takes 10 seconds).

### 3. Add the webhook as a repo secret

In your repo: **Settings → Secrets and variables → Actions → New repository secret**.

- Name: `DISCORD_WEBHOOK_URL`
- Value: the webhook URL from step 2

### 4. Adjust the price cap (optional)

Edit `.github/workflows/check.yml` and change `PRICE_CAP: "800"` to whatever you want.
Same for `MODEL_FILTER` — set it to `""` to match any chip, or `"M4 Pro"` to be picky.

### 5. Run it once manually to confirm it works

Go to **Actions → Mac mini refurb watcher → Run workflow**. Watch the log; if it found
qualifying listings it'll ping Discord. If not, it'll just say "0 are new since last run".

After that, the cron schedule takes over.

## Notes

- GitHub Actions cron is best-effort — slots may be delayed 5–20 minutes during heavy load.
- Refurb stock at deep discount can sell out in minutes. Treat the alert as a starting gun.
- Apple may change their HTML at any time and break the parser. If alerts dry up, run the
  workflow manually and check the log for "Found 0 Mac mini listings" — that's the tell.
- `seen.json` is committed back to the repo each run so you don't get pinged twice for the
  same listing. The workflow needs `contents: write` permission for this; it's already set.

## Troubleshooting

**Nothing happens / no Discord ping:** Run the workflow manually from the Actions tab and
read the log. Either the parser found nothing, nothing was under your cap, or the webhook
URL is wrong.

**"Resource not accessible by integration" on the commit step:** Go to **Settings → Actions
→ General → Workflow permissions** and select **Read and write permissions**.

**Alerts for the same item over and over:** `seen.json` isn't being committed. Check the
last step of the workflow log.
