COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo docker compose || echo docker-compose)

.PHONY: dev test eval deploy weights demo

weights:
	AFTERIMAGE_WEIGHTS_DIR=models python3 services/perception/weights.py

dev: weights
	$(COMPOSE) up --build

test: weights
	$(COMPOSE) run --rm --build app python -m pytest services/ -v; status=$$?; $(COMPOSE) down; exit $$status

demo: weights
	$(COMPOSE) run --rm --build app python -m services.agent.demo; status=$$?; $(COMPOSE) down; exit $$status

eval:
	@echo "eval: not implemented yet (week 7)" && exit 1

deploy:
	@echo "deploy: not implemented yet (week 6)" && exit 1
