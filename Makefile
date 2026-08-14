.PHONY: up down seed run test reset

up:
	docker compose up -d

down:
	docker compose down

seed:
	PYTHONPATH=src .venv/bin/python -m cvlizer.seed

run:
	PYTHONPATH=src .venv/bin/python -m cvlizer.slack_app

test:
	PYTHONPATH=src .venv/bin/pytest tests/

reset:
	docker compose down -v
	docker compose up -d
