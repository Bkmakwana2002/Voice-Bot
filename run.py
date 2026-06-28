"""Single-command entrypoint.

With --tunnel, this starts cloudflared, auto-detects its public URL, writes it into
.env, starts the relay server, verifies the whole path is reachable from the public
internet, then places the requested calls. That removes the #1 source of failures:
stale trycloudflare URLs.

Examples
--------
    python run.py --all --tunnel             # recommended: manage everything
    python run.py --scenario 07-closed-day --tunnel
    python run.py --all                      # use the PUBLIC_URL already in .env
    python run.py --serve-only --tunnel      # serve + tunnel, drive calls elsewhere
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import httpx

from src import config, scenarios

ENV_PATH = Path(__file__).resolve().parent / ".env"


def _wait_for_local_health(timeout_s: int = 20) -> bool:
    url = f"http://127.0.0.1:{config.PORT}/health"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _wait_for_public_health(base_url: str, timeout_s: int = 75) -> bool:
    """trycloudflare warns the URL 'may take some time to be reachable'."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if httpx.get(f"{base_url}/health", timeout=5).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


def _set_public_url_in_env(url: str) -> None:
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    out, found = [], False
    for ln in lines:
        if ln.strip().startswith("PUBLIC_URL="):
            out.append(f"PUBLIC_URL={url}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"PUBLIC_URL={url}")
    ENV_PATH.write_text("\n".join(out) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PGAI patient simulator.")
    parser.add_argument("--scenario", help="scenario id to run")
    parser.add_argument("--all", action="store_true", help="run every scenario")
    parser.add_argument("--serve-only", action="store_true", help="only start the server")
    parser.add_argument("--tunnel", action="store_true",
                        help="start cloudflared and auto-wire its URL (recommended)")
    parser.add_argument("--gap", type=int, default=10, help="seconds between calls")
    args = parser.parse_args()

    tunnel_proc = None
    if args.tunnel:
        from src import tunnel
        print("Starting cloudflared tunnel ...")
        try:
            tunnel_proc, public_url = tunnel.start_cloudflared(config.PORT)
        except RuntimeError as exc:
            print(f"Tunnel error: {exc}")
            sys.exit(1)
        print(f"Tunnel URL: {public_url}")
        _set_public_url_in_env(public_url)
        config.PUBLIC_URL = public_url  # update in-memory for the caller in this process

    problems = config.validate_runtime_env()
    if problems:
        print("Environment is not ready:")
        for p in problems:
            print(f"  - {p}")
        if tunnel_proc:
            tunnel_proc.terminate()
        sys.exit(1)

    # The server is a fresh process; it reads the (now-updated) .env on import.
    server = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "src.server:app",
        "--host", "0.0.0.0", "--port", str(config.PORT),
    ])
    try:
        if not _wait_for_local_health():
            print("Relay server failed to become healthy locally.")
            return
        print(f"Relay server healthy on port {config.PORT}.")

        if args.tunnel:
            print("Verifying the tunnel reaches the relay from the public internet ...")
            if _wait_for_public_health(config.PUBLIC_URL):
                print("Tunnel verified — Twilio will be able to reach the relay.")
            else:
                print("Note: couldn't confirm the tunnel from this machine. This is often "
                      "a false alarm on cellular/NAT (your laptop can't reach its own "
                      "public URL even though Twilio can). Proceeding — watch for the "
                      "[twiml] and [ws] lines below to confirm Twilio actually connects.")

        if args.serve_only:
            print(f"Serving at {config.PUBLIC_URL}. Press Ctrl+C to stop.")
            server.wait()
            return

        from src import caller  # import after server binds the port

        if args.all:
            ids = scenarios.all_ids()
        elif args.scenario:
            ids = [args.scenario]
        else:
            parser.error("pass --scenario <id>, --all, or --serve-only")
            return

        for i, sid in enumerate(ids):
            caller.run_scenario(sid)
            if i < len(ids) - 1:
                time.sleep(args.gap)

        print("Done. Recordings in recordings/, transcripts in transcripts/.")
        print("Next: python -m src.analyze   to triage bugs.")
    finally:
        server.terminate()
        if tunnel_proc:
            tunnel_proc.terminate()


if __name__ == "__main__":
    main()
