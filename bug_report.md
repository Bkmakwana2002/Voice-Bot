# Bug Report — Pretty Good AI voice agent

Issues found while testing the agent at +1-805-439-8008. Each entry says **what
happened**, **why it's a problem**, and **where to find it** (transcript file +
timestamp, plus the matching recording in `recordings/`). `analyze.py` produced the
first-pass candidates; everything below was confirmed by listening to the call.

> Fill this in after running calls. Template entries below — delete and replace.

---

### Bug 1: <one-line summary>

- **Severity:** High / Medium / Low
- **Scenario:** `07-closed-day`
- **Where:** `transcripts/<file>.txt` at `01:23` · `recordings/<file>.mp3`
- **What happened:** When the patient asked "Can I come in this Sunday at 10am?",
  the agent responded "..." (quote it).
- **Why it's a problem:** ... (e.g. confirmed a slot on a day the office is closed,
  never checked hours).
- **Expected:** ... (e.g. inform the patient the office is closed weekends and offer
  the next available weekday).

---

### Bug 2: <one-line summary>

- **Severity:**
- **Scenario:**
- **Where:**
- **What happened:**
- **Why it's a problem:**
- **Expected:**

---

## Scenario coverage

| # | Scenario | Call | Result | Notable issues |
|---|----------|------|--------|----------------|
| 01 | Simple scheduling | | | |
| 02 | Reschedule | | | |
| 03 | Cancel | | | |
| 04 | Medication refill | | | |
| 05 | Office hours | | | |
| 06 | Location + insurance | | | |
| 07 | Closed-day (edge) | | | |
| 08 | Ambiguous request (edge) | | | |
| 09 | Interruptions / barge-in (edge) | | | |
| 10 | Mid-call corrections (edge) | | | |
| 11 | Out-of-scope (edge) | | | |
| 12 | Rambling caller (edge) | | | |
