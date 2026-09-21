COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo docker compose || echo docker-compose)

.PHONY: dev build test lint typecheck verify-runtime eval deploy weights demo

weights:
	AFTERIMAGE_WEIGHTS_DIR=models python3 services/perception/weights.py

dev: weights
	$(COMPOSE) up --build

build:
	$(COMPOSE) build app

test: weights
	$(COMPOSE) run --rm --build app python -m pytest services/ eval/ -v --cov=services --cov-report=term-missing --cov-fail-under=90; status=$$?; $(COMPOSE) down; exit $$status

verify-runtime:
	$(COMPOSE) run --rm app python -m pytest services/perception/tests/test_opencv5.py -v -s

lint:
	$(COMPOSE) run --rm --no-deps app ruff check services/ eval/

typecheck:
	$(COMPOSE) run --rm --no-deps app mypy services/ eval/

demo: weights
	$(COMPOSE) run --rm --build app python -m services.agent.demo; status=$$?; $(COMPOSE) down; exit $$status

eval: weights
	$(COMPOSE) run --rm --build app python -m eval.run_eval $(ARGS); status=$$?; $(COMPOSE) down; exit $$status

deploy:
	./deploy.sh
