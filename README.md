# Black Fox Hackathon — NASA Space Apps Challenge 2026

Website for **blackfoxhackathon.hu** (Hungarian) and **blackfoxhackathon.online** (English).
A small server-side rendered Python site: FastAPI + Jinja2, no JavaScript build step.

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://127.0.0.1:8000  (?lang=hu / ?lang=en)
```

"Ask the Fox" (`/ask`) needs `BLACKFOX_AI_KEY` (and optionally `BLACKFOX_AI_URL`,
`BLACKFOX_AI_MODEL`) — it calls the VPS's AI API, which rotates the Groq keys and
falls back between models.

## Layout

| Path | What |
|---|---|
| `app/main.py` | routes: `/`, `/ask` (GET/POST), `/healthz`, 404 page |
| `app/i18n.py` | **all page text**, Hungarian + English — edit the copy here |
| `app/ai.py` | AI API client + safe Markdown → HTML for answers |
| `app/templates/` | Jinja2 templates |
| `app/static/` | CSS, logo |
| `deploy/` | copies of the VPS setup (systemd units, nginx, update + go-live scripts) |

## Deployment (automatic)

Push to the default branch (`main`) and the VPS is live within about a minute:

- `blackfox-update.timer` runs `/usr/local/sbin/blackfox-update` every minute. If the
  GitHub commit **or** the checked-out branch differs (or the deploy tree was modified),
  it hard-resets `/opt/blackfox/site` to `origin/<branch>`, installs `requirements.txt`
  if it changed, restarts `blackfox.service` and checks `/healthz`.
- If the new commit does not come up healthy it rolls back to the previous one and
  skips the broken commit until a newer one is pushed.
- Branch: `BLACKFOX_BRANCH` in `/etc/blackfox.env` (`auto` = the repo's GitHub default branch).
- Logs: `journalctl -u blackfox-update -u blackfox`.

nginx proxies both domains to `127.0.0.1:8086`; `blackfox-golive.timer` issues the
Let's Encrypt certificates once the DNS records point at the VPS.
