.EXPORT_ALL_VARIABLES:
DOTENV_FILE ?= .env

-include $(DOTENV_FILE)

.PHONY: install
install:
	CASS_DRIVER_NO_CYTHON=1
	@pip install -e ".[cassandra,sqlalchemy,axonserver,axon,ray,django,testing,dev,docs]"

.PHONY: docker-pull
docker-pull:
	@docker-compose pull

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
	@docker-compose down -v --remove-orphans

.PHONY: docker-logs
docker-logs:
	@docker-compose logs --follow --tail=1000


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
	@coverage run \
		--concurrency=multiprocessing \
		-m unittest discover \
		eventsourcing.tests -vv --failfast
	@coverage combine
	@coverage report
	@coverage html


.PHONY: quicktest
quicktest:
	QUICK_TESTS_ONLY=1
	@coverage run -m unittest discover eventsourcing.tests -vv
	@coverage combine
	@coverage report
	@coverage html


.PHONY: docs
docs:
	cd docs && make html


.PHONY: brew_services_start
brew_services_start:
	brew services start mysql
	brew services start postgresql
	brew services start redis
	~/axonserver/axonserver.jar &
	cassandra -f &

.PHONY: brew_services_stop
brew_services_stop:
	brew services stop mysql
	brew services stop postgresql
	brew services stop redis
	pkill -15 java
