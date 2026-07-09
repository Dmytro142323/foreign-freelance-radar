# Foreign Freelance Radar Cloud

Free cloud runner for `foreign_freelance_radar.py` using GitHub Actions.

It runs every 2 hours and sends filtered freelance project cards to Telegram.

## Enabled source groups

- Freelancer.com public active projects API
- PeoplePerHour public project pages
- Guru public project pages, including PayPal-friendly marketplace notes
- Algora public bounty pages
- Public Telegram feeds with Upwork/Freelancer/freelance-project style reposts

Disabled fallback sources are kept in the script for Workana, Truelancer, and extra Telegram feeds. Enable them only if their public pages/channels are useful for your region and do not return too much noise.

## Required GitHub Secrets

Add these in:

`GitHub repo → Settings → Secrets and variables → Actions → New repository secret`

Required secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Manual run

Open:

`Actions → Foreign Freelance Radar → Run workflow`

## Schedule

The workflow runs every 2 hours:

```yaml
17 */2 * * *
```

GitHub free scheduled jobs can be delayed a little. If the repository becomes inactive for a long time, GitHub may pause scheduled workflows; manual runs keep it alive.

## Safety

This script only searches, filters, saves results, and sends Telegram cards. It does not auto-apply, auto-message, or spam clients.
