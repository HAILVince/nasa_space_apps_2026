# Workspace 5 — Deploy (VPS)

Copies of what is installed on the server. Changing a file here does **not** change the
server by itself: after merging, install it (e.g. `sudo install -m644 deploy/blackfox.service
/etc/systemd/system/` + `systemctl daemon-reload`) or ask the server admin.

| File | Installed as | What |
|---|---|---|
| `blackfox.service` | `/etc/systemd/system/` | runs `uvicorn app.main:app` on 127.0.0.1:8086, data in `/var/lib/blackfox` |
| `blackfox-update` + `.service` + `.timer` | `/usr/local/sbin/`, systemd | every minute: pull `main`, restart, health-check, auto-rollback |
| `blackfox-golive` + `.service` + `.timer` | `/usr/local/sbin/`, systemd | Let's Encrypt certificates once DNS points here |
| `nginx-blackfox*.conf` | `/etc/nginx/sites-available/`, `snippets/` | the two domains, HTTPS redirect (Cloudflare-safe), `/api/chat` timeout + rate limit |

Logs: `journalctl -u blackfox -u blackfox-update`. Test: `pytest tests/deploy`.

## AI key on the server

The site talks to the key manager (`ai_api.service`) over loopback, `http://127.0.0.1:8084/v1`.
`BLACKFOX_AI_KEY` in `/etc/blackfox.env` is sent when set; if it is missing or the key manager
rejects it, the site repeats the call without a key, which works when the key manager accepts
local callers. Commands typed on the server (`python -m flame.ingest extract`,
`python -m blackfox.collect ...`) read `/etc/blackfox.env` themselves, so they use the same
settings as the service (the file must be readable by the user running them).

Check it from anywhere: `curl https://blackfoxhackathon.hu/api/ai/status`. `problem` is empty when
all is well, otherwise `auth` (key rejected), `no_key`, `unreachable` (key manager not running) or
`busy`. Failed answers are logged with the reason: `journalctl -u blackfox | grep "AI answer failed"`.
`BLACKFOX_ASKS_PER_MINUTE` (default 6) is the AI chat limit per IP address; people behind one
Wi-Fi share it.

## Research database on the server

The JSON research database (`blackfox/db/knowledge/`) arrives with the code. On the first research
question after an update the service builds its search index in `/var/lib/blackfox` (a few seconds,
about 30 MB of memory). Optional: download the full report texts too (several GB, never more than
`--max-gb`; can be stopped and continued):

```bash
cd /opt/blackfox/site && sudo -u blackfox BLACKFOX_DATA_DIR=/var/lib/blackfox /opt/blackfox/venv/bin/python -m blackfox.collect --max-gb 30 fulltext
```

Details: `blackfox/db/README.md`.

Local vector search adds an ONNX embedding model and PDF parsing. Install the updated
`blackfox.service` (1 GB memory cap) before enabling it on an existing server.
The app detects a cgroup memory cap below 768 MB and leaves vector search unavailable
with an actionable status error, preserving keyword research.
For a server that cannot accommodate the model, set `BLACKFOX_VECTOR_ENABLED=false`;
keyword research stays available. First startup downloads a public model into the service's
writable state directory and builds the index in the background. Monitor
`/api/research/vector/status`; `extraction_errors` lists PDF pages that could not be parsed.
