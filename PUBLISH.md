# Publishing to GitHub

A checklist for getting this repo public and submission-ready. The local repo is
already initialized and has one commit.

## 0. Final safety check (do this every time before pushing)

```bash
# Confirm .env is NOT tracked (only .env.example should appear):
git ls-files | grep -i env

# Confirm no secrets are staged anywhere:
git grep -nE "sk-|AC[0-9a-f]{32}" -- ':!.env.example' || echo "no secrets found"
```

If `.env` shows up in the first command, stop and run `git rm --cached .env`.

## 1. Create the empty GitHub repo

Pick one.

**GitHub CLI (easiest):**
```bash
gh repo create pgai-patient-simulator --public --source=. --remote=origin --push
```
That creates the remote, links it, and pushes in one step — you're done, skip to step 4.

**Web UI:** go to https://github.com/new, name it `pgai-patient-simulator`, set it
**Public**, and do NOT initialize with a README/license (you already have one).

## 2. Link the remote (only if you used the web UI)

```bash
git remote add origin https://github.com/<your-username>/pgai-patient-simulator.git
```

## 3. Push

```bash
git branch -M main
git push -u origin main
```

## 4. Add your evidence, then push again

Before submitting you must include real artifacts (the 10+ call minimum):

```bash
# after running calls, the recordings/ and transcripts/ folders fill up
git add recordings/ transcripts/ bug_report.md
git commit -m "Add call recordings, transcripts, and bug report"
git push
```

Recordings and transcripts are intentionally NOT gitignored, so they'll be included.
Make sure recordings are `.mp3` or `.ogg` (the caller saves `.mp3`) — that format is
required by the submission.

## 5. Submission form

Have these ready for the Pretty Good AI submission form:

- [ ] Public GitHub repo URL
- [ ] Loom walkthrough link (≤5 min: approach + what you built)
- [ ] Loom screen recording of you prompting AI to debug/fix code (≤5 min)
- [ ] The single phone number you called from, in E.164 (e.g. `+1XXXXXXXXXX`) —
      this is your `TWILIO_FROM_NUMBER`
- [ ] ≥10 calls present as both recording (mp3/ogg) **and** transcript

## Optional polish

- Add a short LICENSE (MIT) if you want.
- Tag the submission commit: `git tag submission-v1 && git push --tags`.
