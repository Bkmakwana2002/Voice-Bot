.PHONY: help install env tunnel run serve one list analyze clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Create venv and install dependencies
	python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

env:  ## Copy the example env file (won't overwrite an existing .env)
	@test -f .env || cp .env.example .env
	@echo "Edit .env with your OpenAI + Twilio credentials and PUBLIC_URL."

tunnel:  ## Start an ngrok tunnel to the relay port (run in its own terminal)
	ngrok http 8000

run:  ## Start tunnel + relay and run ALL scenarios end to end
	python run.py --all --tunnel

one:  ## Run a single scenario: make one S=07-closed-day
	python run.py --scenario $(S) --tunnel

serve:  ## Start tunnel + relay only (drive calls from elsewhere)
	python run.py --serve-only --tunnel

list:  ## List available scenario ids
	python -m src.caller --list

analyze:  ## LLM-triage all saved transcripts for candidate bugs
	python -m src.analyze

clean:  ## Remove Python caches
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
