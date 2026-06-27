"""Append-only, timestamped transcript logging for a single call.

We capture BOTH sides:
  - "AGENT"  = the Pretty Good AI phone agent (transcribed from its audio)
  - "PATIENT"= our bot (the text it generated for its own speech)

Each call gets one .txt file under transcripts/.
"""
from __future__ import annotations

import time
from pathlib import Path

TRANSCRIPT_DIR = Path(__file__).resolve().parent.parent / "transcripts"
TRANSCRIPT_DIR.mkdir(exist_ok=True)


class TranscriptWriter:
    def __init__(self, scenario_id: str, call_sid: str | None = None) -> None:
        ts = time.strftime("%Y%m%d-%H%M%S")
        suffix = f"-{call_sid[-6:]}" if call_sid else ""
        self.path = TRANSCRIPT_DIR / f"{ts}-{scenario_id}{suffix}.txt"
        self._start = time.monotonic()
        self._fh = self.path.open("w", encoding="utf-8")
        self._header(scenario_id, call_sid)

    def _header(self, scenario_id: str, call_sid: str | None) -> None:
        self._fh.write(f"# Scenario: {scenario_id}\n")
        self._fh.write(f"# Call SID: {call_sid or 'n/a'}\n")
        self._fh.write(f"# Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        self._fh.write("# Speakers: PATIENT = our test bot, AGENT = Pretty Good AI\n")
        self._fh.write("-" * 60 + "\n")
        self._fh.flush()

    def _stamp(self) -> str:
        elapsed = time.monotonic() - self._start
        return f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"

    def line(self, speaker: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self._fh.write(f"[{self._stamp()}] {speaker}: {text}\n")
        self._fh.flush()

    def note(self, text: str) -> None:
        """Log a system note (e.g. interruption detected) inline."""
        self._fh.write(f"[{self._stamp()}] -- {text}\n")
        self._fh.flush()

    def close(self) -> None:
        try:
            self._fh.write("-" * 60 + "\n# Call ended\n")
            self._fh.close()
        except Exception:
            pass
