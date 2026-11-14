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
