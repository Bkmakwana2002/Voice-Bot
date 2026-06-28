"""Manage a cloudflared quick tunnel automatically.

trycloudflare quick tunnels hand out a fresh random URL on every start, which makes
copy-pasting it into .env a constant source of "stale URL" failures. This module
starts cloudflared, scrapes the URL it prints, and hands it back so the app can wire
it in itself — no manual copying.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

_URL_RE = re.compile(r"https://[-a-z0-9]+\.trycloudflare\.com")


def find_cloudflared() -> str | None:
    """Locate the cloudflared binary without depending on a perfectly set PATH.

    Order: $CLOUDFLARED_PATH, then PATH, then a copy dropped in the repo root.
    """
    env_path = os.getenv("CLOUDFLARED_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    on_path = shutil.which("cloudflared")
    if on_path:
        return on_path

    repo_root = Path(__file__).resolve().parent.parent
    for name in ("cloudflared.exe", "cloudflared"):
        candidate = repo_root / name
        if candidate.exists():
            return str(candidate)
    return None


def start_cloudflared(port: int, timeout: int = 45) -> tuple[subprocess.Popen, str]:
    """Start `cloudflared tunnel --url http://localhost:<port>` and return
    (process, public_url). Raises RuntimeError if cloudflared is missing or no URL
    appears within `timeout` seconds.
    """
    binary = find_cloudflared()
    if not binary:
        raise RuntimeError(
            "cloudflared not found. Easiest fix on Windows: download "
            "cloudflared-windows-amd64.exe from "
            "github.com/cloudflare/cloudflared/releases/latest, rename it to "
            "cloudflared.exe, and drop it in this repo folder. (Or install via "
            "winget/brew and reopen your terminal, or set CLOUDFLARED_PATH.) "
            "Alternatively, start your own tunnel, set PUBLIC_URL in .env, and run "
            "without --tunnel."
        )
    try:
        proc = subprocess.Popen(
            [binary, "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        raise RuntimeError(f"Failed to launch cloudflared at {binary}: {exc!r}") from exc

    url: str | None = None
    recent: list[str] = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline() if proc.stdout else ""
        if not line:
            if proc.poll() is not None:
                break
            time.sleep(0.1)
            continue
        recent.append(line.rstrip())
        recent[:] = recent[-15:]
        match = _URL_RE.search(line)
        if match:
            url = match.group(0)
            break

    if not url:
        proc.terminate()
        raise RuntimeError(
            "Could not detect a cloudflared URL. Last output:\n  "
            + "\n  ".join(recent)
        )

    # The URL is printed before the tunnel is actually usable. Wait until cloudflared
    # reports a registered connection, so we don't hand back a dead URL.
    registered = False
    reg_deadline = time.time() + 25
    while time.time() < reg_deadline:
        line = proc.stdout.readline() if proc.stdout else ""
        if not line:
            if proc.poll() is not None:
                break
            time.sleep(0.1)
            continue
        recent.append(line.rstrip())
        recent[:] = recent[-15:]
        low = line.lower()
        if "registered tunnel connection" in low or "connection registered" in low:
            registered = True
            break

    # Keep draining cloudflared's output so its pipe buffer never fills and blocks it.
    def _drain() -> None:
        if not proc.stdout:
            return
        for _ in proc.stdout:
            pass

    threading.Thread(target=_drain, daemon=True).start()

    if not registered:
        print("  (warning: cloudflared printed a URL but never reported a registered "
              "connection — the corporate network may be blocking the tunnel.)")
    return proc, url
