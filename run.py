"""Single-command entrypoint.

Starts the relay server, waits until it's healthy, then places the requested calls.
Assumes ngrok (or another tunnel) is already pointing PUBLIC_URL at this machine's
PORT — see the README.

Examples
--------
    python run.py --all                      # run every scenario end to end
    python run.py --scenario 07-closed-day   # run one scenario
    python run.py --serve-only               # just run the server (call from elsewhere)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

import httpx

from src import config, scenarios


def _wait_for_health(timeout_s: int = 20) -> bool:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PGAI patient simulator.")
    parser.add_argument("--scenario", help="scenario id to run")
    parser.add_argument("--all", action="store_true", help="run every scenario")
    parser.add_argument("--serve-only", action="store_true", help="only start the server")
    parser.add_argument("--gap", type=int, default=10, help="seconds between calls")
    args = parser.parse_args()

    problems = config.validate_runtime_env()
    if problems:
        print("Environment is not ready:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    server = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "src.server:app",
        "--host", "0.0.0.0", "--port", str(config.PORT),
    ])
    try:
        if not _wait_for_health():
            print("Relay server failed to become healthy.")
            return
        print(f"Relay server healthy on port {config.PORT}.")

        if args.serve_only:
            print("Serving. Press Ctrl+C to stop.")
            server.wait()
            return

        # Import here so the server process above is the one binding the port.
        from src import caller

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


if __name__ == "__main__":
    main()
