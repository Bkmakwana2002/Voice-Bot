"""Place outbound test calls and download their recordings.

Usage (after the relay server is running and reachable at PUBLIC_URL):

    python -m src.caller --scenario 01-schedule-basic
    python -m src.caller --all                 # run every scenario in sequence
    python -m src.caller --list                # show scenario ids

Each call:
  1. starts a Twilio outbound call to the assessment number (and ONLY that number),
  2. points Twilio at /twiml/<scenario> so the audio streams into our relay,
  3. records the call (dual channel),
  4. waits for completion, then downloads the recording as .mp3 into recordings/.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx
from twilio.rest import Client

from . import config, scenarios

RECORDING_DIR = Path(__file__).resolve().parent.parent / "recordings"
RECORDING_DIR.mkdir(exist_ok=True)


def _client() -> Client:
    return Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)


def place_call(scenario_id: str) -> str:
    """Start one outbound call. Returns the Twilio call SID."""
    scenario = scenarios.get(scenario_id)  # validates id early
    config.assert_target_allowed(config.TARGET_NUMBER)  # belt-and-suspenders guard

    client = _client()
    call = client.calls.create(
        to=config.TARGET_NUMBER,
        from_=config.TWILIO_FROM_NUMBER,
        url=f"{config.PUBLIC_URL}/twiml/{scenario.id}",
        record=True,
        recording_channels="dual",
    )
    print(f"[{scenario.id}] call started: {call.sid}")
    return call.sid


def wait_for_completion(call_sid: str, timeout_s: int = 300) -> str:
    """Poll until the call leaves an in-progress state. Returns final status."""
    client = _client()
    deadline = time.time() + timeout_s
    status = "queued"
    while time.time() < deadline:
        call = client.calls(call_sid).fetch()
        status = call.status
        if status in {"completed", "failed", "busy", "no-answer", "canceled"}:
            break
        time.sleep(3)
    print(f"[{call_sid}] final status: {status}")
    return status


def download_recording(call_sid: str, scenario_id: str, timeout_s: int = 60) -> Path | None:
    """Download the call recording as mp3. Returns the saved path or None."""
    client = _client()
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        recordings = client.recordings.list(call_sid=call_sid)
        if recordings:
            rec = recordings[0]
            # Twilio exposes the media at this URL; append .mp3 for that format.
            media_url = (
                f"https://api.twilio.com/2010-04-01/Accounts/"
                f"{config.TWILIO_ACCOUNT_SID}/Recordings/{rec.sid}.mp3"
            )
            resp = httpx.get(
                media_url,
                auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN),
                timeout=30,
                follow_redirects=True,
            )
            resp.raise_for_status()
            out = RECORDING_DIR / f"{scenario_id}-{call_sid[-6:]}.mp3"
            out.write_bytes(resp.content)
            print(f"[{scenario_id}] recording saved: {out.name}")
            return out
        time.sleep(3)
    print(f"[{scenario_id}] no recording found within {timeout_s}s")
    return None


def run_scenario(scenario_id: str) -> None:
    sid = place_call(scenario_id)
    wait_for_completion(sid)
    download_recording(sid, scenario_id)


def _preflight() -> None:
    problems = config.validate_runtime_env()
    if problems:
        print("Environment is not ready:")
        for p in problems:
            print(f"  - {p}")
        print("Fill in .env (see .env.example) and start ngrok first.")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Place PGAI test calls.")
    parser.add_argument("--scenario", help="scenario id to run")
    parser.add_argument("--all", action="store_true", help="run every scenario")
    parser.add_argument("--list", action="store_true", help="list scenario ids")
    parser.add_argument("--gap", type=int, default=10,
                        help="seconds to wait between calls in --all mode")
    args = parser.parse_args()

    if args.list:
        for s in scenarios.SCENARIOS:
            print(f"{s.id:24s} {s.name}")
        return

    _preflight()

    if args.all:
        for i, sid in enumerate(scenarios.all_ids()):
            run_scenario(sid)
            if i < len(scenarios.all_ids()) - 1:
                time.sleep(args.gap)
    elif args.scenario:
        run_scenario(args.scenario)
    else:
        parser.error("pass --scenario <id>, --all, or --list")


if __name__ == "__main__":
    main()
