.PHONY: setup run test clean

PYTHON ?= python3
VENV := .venv
VENV_PY := $(VENV)/bin/python
REPO ?= ./demo_repo
TASK ?= Fix the login API returning 500 when the email is missing.

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PY) -m pip install --upgrade pip -q
	$(VENV_PY) -m pip install -r requirements.txt -q
	@echo "Setup complete. Activate with: source $(VENV)/bin/activate"

run:
	@if [ -z "$$AI_API_KEY" ]; then \
		echo "ERROR: AI_API_KEY is not set. Run: export AI_API_KEY=your-key-here"; \
		exit 1; \
	fi
	$(VENV_PY) -m src.main --repo "$(REPO)" --task "$(TASK)"

test:
	$(VENV_PY) -m pytest -q

clean:
	rm -rf $(VENV) .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
