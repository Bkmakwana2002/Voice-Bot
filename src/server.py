"""Relay server: bridges a Twilio Media Stream to the OpenAI Realtime API.

Audio path
----------
Twilio  --(g711 ulaw 8k, base64)-->  this server  --(append)-->  OpenAI Realtime
Twilio  <--(g711 ulaw 8k, base64)--  this server  <--(deltas)--  OpenAI Realtime

We configure the Realtime session to use g711_ulaw for BOTH input and output, so
audio passes through untouched in both directions. No resampling = fewer glitches
and lower latency, which is the whole ballgame for "coherent voice".

Endpoints
---------
GET/POST /twiml/{scenario_id}  -> returns TwiML that opens a <Stream> to /ws
WS       /ws/{scenario_id}     -> the bridge itself
GET      /health               -> liveness probe used by run.py
"""
from __future__ import annotations

import asyncio
import base64
import json

import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from . import config, scenarios
from .transcripts import TranscriptWriter

app = FastAPI(title="PGAI patient-simulator relay")


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True})


@app.api_route("/twiml/{scenario_id}", methods=["GET", "POST"])
async def twiml(scenario_id: str, request: Request) -> HTMLResponse:
    """TwiML that tells Twilio to stream the call audio to our WebSocket.

    The scenario id is carried in the WS path so the bridge knows which persona
    to load. <Stream> is bidirectional, so the audio we send back is played to
    the agent on the other end of the call.
    """
    ws_url = config.PUBLIC_URL.replace("https://", "wss://").replace("http://", "ws://")
    print(f"[twiml] Twilio fetched TwiML for scenario={scenario_id}; "
          f"telling it to stream to {ws_url}/ws/{scenario_id}")
    vxml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{ws_url}/ws/{scenario_id}" />
  </Connect>
</Response>"""
    return HTMLResponse(content=vxml, media_type="text/xml")


async def _connect_openai(headers: dict):
    """Open the Realtime WS, tolerating both modern and legacy `websockets` APIs.

    websockets >= 14 (and the asyncio client) uses `additional_headers`; the older
    top-level `websockets.connect` uses `extra_headers`. Try both so the relay works
    regardless of the installed version.
    """
    try:
        return await websockets.connect(config.REALTIME_URL, additional_headers=headers)
    except TypeError:
        return await websockets.connect(config.REALTIME_URL, extra_headers=headers)


def _session_update(scenario: scenarios.Scenario) -> dict:
    """The session.update payload that configures the Realtime persona + audio."""
    return {
        "type": "session.update",
        "session": {
            "modalities": ["audio", "text"],
            "instructions": scenario.instructions(),
            "voice": config.REALTIME_VOICE,
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            # Transcribe the AGENT's incoming audio so we can log their side.
            "input_audio_transcription": {"model": "whisper-1"},
            # Server-side VAD handles turn-taking and barge-in for us.
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 600,
            },
            "temperature": 0.8,
        },
    }


@app.websocket("/ws/{scenario_id}")
async def media_stream(ws: WebSocket, scenario_id: str) -> None:
    await ws.accept()
    print(f"[ws] Twilio media stream connected for scenario={scenario_id}")
    try:
        scenario = scenarios.get(scenario_id)
    except KeyError:
        await ws.close(code=1008)
        return

    transcript = TranscriptWriter(scenario_id)
    stream_sid: str | None = None

    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }

    try:
        oai = await _connect_openai(headers)
    except Exception as exc:
        print(f"[ws] FAILED to connect to OpenAI Realtime: {exc!r}")
        transcript.note(f"could not connect to OpenAI Realtime: {exc!r}")
        transcript.close()
        await ws.close()
        return

    print("[ws] connected to OpenAI Realtime")
    try:
        # 1) Configure the session (persona + g711 audio + VAD).
        await oai.send(json.dumps(_session_update(scenario)))

        # 2) Kick off the call: have the bot deliver its opening line first, so the
        #    conversation starts naturally once the agent picks up and greets us.
        await oai.send(json.dumps({
            "type": "response.create",
            "response": {
                "instructions": (
                    f"The practice's agent has just answered. Open the call by saying, "
                    f"naturally and briefly: \"{scenario.opening}\""
                )
            },
        }))

        async def twilio_to_openai() -> None:
            nonlocal stream_sid
            try:
                async for raw in ws.iter_text():
                    data = json.loads(raw)
                    event = data.get("event")
                    if event == "start":
                        stream_sid = data["start"]["streamSid"]
                        transcript.note(f"stream started ({stream_sid})")
                    elif event == "media":
                        # Twilio g711 ulaw payload -> straight into the Realtime buffer.
                        await oai.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": data["media"]["payload"],
                        }))
                    elif event == "stop":
                        transcript.note("stream stopped")
                        break
            except WebSocketDisconnect:
                pass

        async def openai_to_twilio() -> None:
            nonlocal stream_sid
            async for raw in oai:
                evt = json.loads(raw)
                etype = evt.get("type")

                if etype == "response.audio.delta" and stream_sid:
                    # Realtime g711 ulaw delta -> back to Twilio to play to the agent.
                    await ws.send_text(json.dumps({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": evt["delta"]},
                    }))

                elif etype == "input_audio_buffer.speech_started" and stream_sid:
                    # The agent started talking while our bot was speaking: barge-in.
                    # Clear whatever audio Twilio still has buffered so we stop talking.
                    transcript.note("barge-in: agent started speaking, clearing playback")
                    await ws.send_text(json.dumps({
                        "event": "clear",
                        "streamSid": stream_sid,
                    }))

                elif etype == "conversation.item.input_audio_transcription.completed":
                    transcript.line("AGENT", evt.get("transcript", ""))

                elif etype == "response.audio_transcript.done":
                    transcript.line("PATIENT", evt.get("transcript", ""))

                elif etype == "error":
                    transcript.note(f"openai error: {evt.get('error')}")

        try:
            await asyncio.gather(twilio_to_openai(), openai_to_twilio())
        except websockets.ConnectionClosed:
            pass
    finally:
        print(f"[ws] call ended for scenario={scenario_id}")
        try:
            await oai.close()
        except Exception:
            pass
        transcript.close()
