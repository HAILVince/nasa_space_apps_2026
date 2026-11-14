"""Deploy workspace (deploy/): config files stay valid and consistent with the app."""

import subprocess
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"


def test_shell_scripts_parse():
    for name in ("blackfox-update", "blackfox-golive"):
        subprocess.run(["bash", "-n", str(DEPLOY / name)], check=True)


def test_service_runs_the_app_with_writable_state():
    unit = (DEPLOY / "blackfox.service").read_text()
    assert "app.main:app" in unit and "--port 8086" in unit
    assert "StateDirectory=blackfox" in unit and "ProtectSystem=strict" in unit


def test_update_script_checks_health_and_rolls_back():
    s = (DEPLOY / "blackfox-update").read_text()
    assert "/healthz" in s and "bad" in s


def test_nginx_proxies_chat_with_long_timeout():
    loc = (DEPLOY / "nginx-blackfox-locations.conf").read_text()
    assert "location = /api/chat" in loc and "proxy_read_timeout" in loc
