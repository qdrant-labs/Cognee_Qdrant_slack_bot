PY := ../.venv/bin/python

.PHONY: help setup ingest demo contractor skill check

help:
	@echo "make setup       create venv + install deps"
	@echo "make check       verify .env and reachability of Qdrant + the LLM"
	@echo "make ingest      Slack export -> typed decision graph (calls the LLM once)"
	@echo "make index       (re)create the Qdrant payload index the ACL filter needs"
	@echo "make demo        the side-by-side comparison, as the backend lead"
	@echo "make contractor  same question at contractor clearance"
	@echo "make skill       compile the graph into .claude/skills/"

setup:
	uv venv --python 3.12 ../.venv
	uv pip install --python $(PY) -r requirements.txt

check:
	$(PY) check_env.py

ingest:
	$(PY) ingest.py

index:
	$(PY) index_payload.py

demo:
	$(PY) demo.py

contractor:
	$(PY) demo.py --as contractor

skill:
	$(PY) compile_skill.py
