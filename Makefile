COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo docker compose || echo docker-compose)

.PHONY: dev test eval deploy

dev:
	$(COMPOSE) up --build

test:
	$(COMPOSE) run --rm --build app python -m pytest services/ -v; status=$$?; $(COMPOSE) down; exit $$status

eval:
	@echo "eval: not implemented yet (week 7)" && exit 1

deploy:
	@echo "deploy: not implemented yet (week 6)" && exit 1
