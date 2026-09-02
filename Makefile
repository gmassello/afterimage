COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo docker compose || echo docker-compose)

.PHONY: dev test eval deploy weights demo

weights:
	AFTERIMAGE_WEIGHTS_DIR=models python3 services/perception/weights.py

dev: weights
	$(COMPOSE) up --build

test: weights
	$(COMPOSE) run --rm --build app python -m pytest services/ eval/ -v; status=$$?; $(COMPOSE) down; exit $$status

demo: weights
	$(COMPOSE) run --rm --build app python -m services.agent.demo; status=$$?; $(COMPOSE) down; exit $$status

eval: weights
	$(COMPOSE) run --rm --build app python -m eval.run_eval $(ARGS); status=$$?; $(COMPOSE) down; exit $$status

deploy:
	./deploy.sh
