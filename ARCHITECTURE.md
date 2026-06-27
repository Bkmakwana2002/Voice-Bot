# Architecture

The system is a thin real-time audio bridge with a thinking layer on top. A Python
orchestrator (`caller.py`) uses Twilio to place an outbound call to the assessment
line and instructs Twilio, via TwiML, to open a bidirectional Media Stream to a small
FastAPI server (`server.py`). That server relays the call's audio to the **OpenAI
Realtime API**, which is configured with a *patient persona and a goal* (defined in
`scenarios.py`) rather than a rigid script. The Realtime model listens to the Pretty
Good AI agent, decides what the patient would say, and speaks back through the same
WebSocket onto the live call. Twilio records the call (dual channel) and the Realtime
API transcribes both sides, which we timestamp into per-call transcript files;
recordings are downloaded as mp3 once the call completes, and `analyze.py` does a
first-pass LLM triage of the transcripts against a bug rubric for a human to confirm.

The key design choice is **speech-to-speech over a STT→LLM→TTS cascade**: the
assessment's #1 criterion is a coherent, natural voice conversation, and a single
realtime model with server-side voice-activity detection gives the lowest latency,
the most natural turn-taking, and built-in barge-in handling with far less code than
stitching three services together. The second deliberate choice is **g711 μ-law
passthrough** — both Twilio and the Realtime session speak g711 μ-law at 8 kHz, so we
forward audio frames untouched in both directions, avoiding resampling artifacts and
the latency that most often makes these bots sound glitchy. Persona-and-goal prompting
(plus a shared style guide enforcing short, human turns) keeps the bot steering each
call toward its test objective like a real caller instead of a benchmark runner, while
the hardcoded target-number guard in `config.py` makes it structurally impossible to
dial anything but the assessment line.
