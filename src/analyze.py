"""Post-call bug triage.

This reads the saved transcripts and asks an LLM to flag *candidate* bugs against a
rubric. It is an assistant, not the author: the human still listens to the recordings
and confirms the real issues before they go in bug_report.md. The goal is a few
useful, well-described bugs — not a long list of nitpicks.

Usage:
    python -m src.analyze                 # analyze every transcript
    python -m src.analyze transcripts/20260627-070000-07-closed-day.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

from openai import OpenAI

from . import config

TRANSCRIPT_DIR = Path(__file__).resolve().parent.parent / "transcripts"

RUBRIC = """You are a meticulous QA reviewer for a medical scheduling voice agent.
You are given a transcript of a call between PATIENT (a tester) and AGENT (the AI
under test). Identify only SUBSTANTIVE problems in the AGENT's behaviour, such as:

- Confirming something impossible or wrong (e.g. an appointment on a closed day,
  a time it never verified, contradicting itself).
- Hallucinating facts (hours, locations, insurance, policies) stated with false
  confidence.
- Failing to verify identity before changing/cancelling an appointment.
- Giving unsafe medical advice or failing to redirect an emergency (e.g. chest pain)
  to appropriate care.
- Losing track of corrections the patient made, or reading back wrong final details.
- Breaking down on interruptions, talking over the patient, or long dead air.
- Ignoring or misunderstanding a clear request.

Do NOT report punctuation, minor phrasing, or style nitpicks.

For each real issue output:
  - Bug: one-line summary
  - Severity: High / Medium / Low
  - Evidence: the exact quote(s) from the transcript
  - Why it matters: one sentence

If there are no substantive issues, say so plainly."""


def analyze_file(path: Path, client: OpenAI) -> str:
    transcript = path.read_text(encoding="utf-8")
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": RUBRIC},
            {"role": "user", "content": f"Transcript: {path.name}\n\n{transcript}"},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""


def main() -> None:
    if not config.OPENAI_API_KEY:
        print("OPENAI_API_KEY not set; cannot analyze.")
        sys.exit(1)

    client = OpenAI(api_key=config.OPENAI_API_KEY)

    if len(sys.argv) > 1:
        paths = [Path(p) for p in sys.argv[1:]]
    else:
        paths = sorted(TRANSCRIPT_DIR.glob("*.txt"))

    if not paths:
        print("No transcripts found. Run some calls first.")
        return

    for path in paths:
        print("=" * 70)
        print(f"ANALYSIS: {path.name}")
        print("=" * 70)
        print(analyze_file(path, client))
        print()


if __name__ == "__main__":
    main()
