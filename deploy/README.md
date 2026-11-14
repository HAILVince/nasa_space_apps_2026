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

## Research database on the server

The JSON research database (`blackfox/db/knowledge/`) arrives with the code. On the first research
question after an update the service builds its search index in `/var/lib/blackfox` (a few seconds,
about 30 MB of memory). Optional: download the full report texts too (several GB, never more than
`--max-gb`; can be stopped and continued):

```bash
cd /opt/blackfox/site && sudo -u blackfox BLACKFOX_DATA_DIR=/var/lib/blackfox /opt/blackfox/venv/bin/python -m blackfox.collect --max-gb 30 fulltext
```

Details: `blackfox/db/README.md`.
