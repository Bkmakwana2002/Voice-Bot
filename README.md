# PGAI Patient Simulator

An automated voice bot that calls the Pretty Good AI test line, role-plays realistic
patients (scheduling, refills, questions, edge cases), and records + transcribes every
call so its responses can be reviewed for bugs.

It only ever dials the assessment number, `+1-805-439-8008`. That number is hardcoded
and guarded in `src/config.py` — a bad `.env` value cannot make it call anything else.

## How it works (short version)

Twilio places an outbound call and streams the live audio over a WebSocket to this
app, which relays it to the **OpenAI Realtime API** (speech-to-speech). The Realtime
session is given a *patient persona + goal* and talks back through Twilio onto the
call. Audio is passed through as g711 μ-law in both directions (no resampling) for low
latency and clean audio. Both sides are transcribed and the call is recorded to mp3.
See [ARCHITECTURE.md](ARCHITECTURE.md) for the reasoning.

```
caller.py ──> Twilio (outbound call) ──> +1 805 439 8008 (PGAI agent)
                   │  media stream (ws)
                   ▼
              server.py  ◀────────────▶  OpenAI Realtime API
                   │
                   ├─ transcripts/*.txt   (both sides, timestamped)
                   └─ recordings/*.mp3     (downloaded after each call)
```

## Setup

1. **Python deps**

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Credentials** — copy the example env and fill it in:

   ```bash
   cp .env.example .env
   # edit .env: OpenAI key, Twilio SID/token, your Twilio number
   ```

3. **Expose the relay** so Twilio can reach it. In a separate terminal:

   ```bash
   ngrok http 8000
   ```

   Copy the `https://...ngrok-free.app` URL into `PUBLIC_URL` in `.env`.

## Run

Single command after setup (starts the server, waits for it, then runs the calls):

```bash
python run.py --all                      # run all 12 scenarios
python run.py --scenario 07-closed-day   # run just one
```

Then triage the transcripts for bugs:

```bash
python -m src.analyze
```

Other handy commands:

```bash
python -m src.caller --list      # list scenario ids
python run.py --serve-only       # just run the relay (drive calls from elsewhere)
```

## Outputs

- `recordings/` — one `.mp3` per call (both sides, dual channel).
- `transcripts/` — one timestamped `.txt` per call, labelling PATIENT (our bot) vs
  AGENT (Pretty Good AI).
- `bug_report.md` — the curated, human-confirmed issues.

## Cost

Typical run (≈12 short calls) stays well under $20: Twilio outbound voice + recording
is a few cents per minute, and the OpenAI Realtime audio is the main cost. Use a
`-mini` realtime model via `REALTIME_MODEL` in `.env` to cut it further.

## Notes & limits

- `PUBLIC_URL` must be reachable by Twilio; ngrok is the simplest option for testing.
- OpenAI occasionally renames the Realtime model — override `REALTIME_MODEL` in `.env`
  if the default 404s.
- This is a take-home prototype, not production infra: no retries/queueing, single
  process, local tunnel.
