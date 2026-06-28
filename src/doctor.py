"""End-to-end connectivity doctor.

Reproduces the exact path Twilio uses to reach your relay — but from your own
laptop, and without placing a phone call. Run it while the relay server AND the
tunnel (cloudflared/ngrok) are both running:

    # terminal 1
    python run.py --serve-only
    # terminal 2
    cloudflared tunnel --url http://localhost:8000   (and put its URL in .env)
    # terminal 3
    python -m src.doctor

It checks four things in order and stops at the first failure:
  1. PUBLIC_URL is reachable from the public internet  (GET /health)
  2. The TwiML endpoint serves valid XML                (GET /twiml/<scenario>)
  3. The media-stream WebSocket accepts a connection    (wss /ws/<scenario>)
  4. The bot actually produces audio                    (we receive 'media' frames)

If step 4 passes, your whole stack works and the only remaining variable is
Twilio itself (account/trial/region). If it fails earlier, the step number tells
you which link is broken.
"""
from __future__ import annotations

import asyncio
import json
import sys

import httpx
import websockets

from . import config

SCENARIO = "01-schedule-basic"


def _fail(step: str, msg: str) -> None:
    print(f"\n  FAIL [{step}] {msg}")
    print("\nStop here — fix this before placing calls. See notes above.")
    sys.exit(1)


async def main() -> None:
    problems = config.validate_runtime_env()
    if problems:
        for p in problems:
            print(f"  - {p}")
        _fail("env", "environment is not fully configured")

    base = config.PUBLIC_URL
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
    print(f"Using PUBLIC_URL = {base}")

    # 1) tunnel + server reachable from the public internet
    print("\n[1/4] GET /health through the tunnel ...")
    try:
        r = httpx.get(f"{base}/health", timeout=10)
        if r.status_code != 200:
            _fail("health", f"got HTTP {r.status_code}. Is the tunnel pointed at "
                            f"port {config.PORT} and the relay running?")
        print("      OK — tunnel reaches the relay.")
    except Exception as exc:
        _fail("health", f"could not reach {base} ({exc!r}). The tunnel URL in .env is "
                        f"probably stale/down — restart cloudflared and update PUBLIC_URL.")

    # 2) TwiML serves valid XML
    print("\n[2/4] GET /twiml/<scenario> ...")
    try:
        r = httpx.get(f"{base}/twiml/{SCENARIO}", timeout=10)
        if r.status_code != 200 or "<Stream" not in r.text:
            _fail("twiml", f"unexpected TwiML response (HTTP {r.status_code}):\n{r.text[:300]}")
        print("      OK — TwiML served. Stream target:")
        for line in r.text.splitlines():
            if "Stream" in line:
                print(f"        {line.strip()}")
    except Exception as exc:
        _fail("twiml", f"TwiML request failed ({exc!r}).")

    # 3 + 4) WebSocket upgrade, then wait for the bot's audio
    print("\n[3/4] Opening media-stream WebSocket ...")
    url = f"{ws_base}/ws/{SCENARIO}"
    try:
        async with websockets.connect(url, open_timeout=15) as ws:
            print("      OK — WebSocket upgrade succeeded.")
            # Mimic Twilio's first messages so the server sets a streamSid.
            await ws.send(json.dumps({"event": "connected", "protocol": "Call"}))
            await ws.send(json.dumps({
                "event": "start",
                "start": {"streamSid": "DOCTORSTREAM", "callSid": "DOCTORCALL"},
            }))

            print("\n[4/4] Waiting up to 20s for the bot to produce audio ...")
            media_frames = 0

            async def _drain() -> None:
                nonlocal media_frames
                async for raw in ws:
                    evt = json.loads(raw)
                    if evt.get("event") == "media":
                        media_frames += 1
                        if media_frames == 1:
                            print("      Receiving audio from the bot ...")
                        if media_frames >= 25:
                            return

            try:
                await asyncio.wait_for(_drain(), timeout=20)
            except asyncio.TimeoutError:
                pass

            if media_frames == 0:
                _fail("audio", "WebSocket connected but the bot produced NO audio. "
                               "Most likely the relay could not reach OpenAI Realtime "
                               "(corporate proxy blocking wss to api.openai.com, bad "
                               "OPENAI_API_KEY, or wrong REALTIME_MODEL). Check the relay "
                               "terminal for a '[ws] FAILED to connect to OpenAI' line.")
            print(f"      OK — received {media_frames} audio frames from the bot.")
    except Exception as exc:
        _fail("websocket", f"could not open the media-stream WebSocket ({exc!r}). The "
                           f"tunnel may not be forwarding WebSocket upgrades, or it is down.")

    print("\nALL CHECKS PASSED. Your relay + OpenAI path works end to end.")
    print("If real calls still fail, the issue is Twilio-side: check the Twilio Console")
    print("call log for the exact error, and confirm the account is upgraded (not trial).")


if __name__ == "__main__":
    asyncio.run(main())
