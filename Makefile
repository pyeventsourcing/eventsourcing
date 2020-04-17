.EXPORT_ALL_VARIABLES:
COMPOSE_FILE ?= dev/docker-compose.yaml
COMPOSE_PROJECT_NAME ?= eventsourcing
DOTENV_FILE ?= .env

-include $(DOTENV_FILE)

.PHONY: install
install:
	@pip install -e ".[cassandra,sqlalchemy,axonserver,axon,ray,django,testing,dev,docs]"

.PHONY: docs
docs:
	cd docs && make html

.PHONY: docker-build
docker-build:
	@docker-compose build

.PHONY: docker-up
docker-up:
	@docker-compose up -d
	@docker-compose ps

.PHONY: docker-stop
docker-stop:
	@docker-compose stop

.PHONY: docker-down
docker-down:
	@docker-compose down --remove-orphans

.PHONY: docker-logs
docker-logs:
	@docker-compose logs --follow


.PHONY: lint-black
lint-black:
	@black --check --diff .

.PHONY: lint-flake8
lint-flake8:
	@flake8 eventsourcing

.PHONY: lint-isort
lint-isort:
	@isort --check-only --diff --recursive .

.PHONY: lint-mypy
lint-mypy:
	@mypy --ignore-missing-imports eventsourcing

.PHONY: lint-dockerfile
lint-dockerfile:
	@docker run --rm -i replicated/dockerfilelint:ad65813 < ./dev/Dockerfile_eventsourcing_requirements

.PHONY: lint
lint: lint-black lint-flake8 lint-isort lint-mypy lint-dockerfile


.PHONY: fmt-isort
fmt-isort:
	@isort -y --recursive .

.PHONY: fmt-black
fmt-black:
	@black .

.PHONY: fmt
fmt: fmt-black fmt-isort


.PHONY: test
test:
	@python -m unittest discover eventsourcing.tests -v
