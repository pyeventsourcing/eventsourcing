.EXPORT_ALL_VARIABLES:
DOTENV_FILE ?= dev/.env

-include $(DOTENV_FILE)

POETRY ?= poetry
POETRY_VERSION=1.5.1
POETRY_INSTALLER_URL ?= https://install.python-poetry.org
PYTHONUNBUFFERED=1
SAMPLES_LINE_LENGTH=70

.PHONY: install-poetry
install-poetry:
	curl -sSL $(POETRY_INSTALLER_URL) | python3
	$(POETRY) --version

.PHONY: install
install:
	$(POETRY) install --extras "crypto postgres_dev docs" -vv $(opts)

.PHONY: install-packages
install-packages:
	$(POETRY) install --no-root --extras "crypto postgres_dev docs" -vv $(opts)

.PHONY: update-packages
update-packages:
	$(POETRY) update -vv

.PHONY: lint
lint: lint-black lint-flake8 lint-isort lint-mypy #lint-dockerfile

.PHONY: lint-black
lint-black:
	$(POETRY) run black --check --diff eventsourcing

.PHONY: lint-flake8
lint-flake8:
	$(POETRY) run flake8 eventsourcing

.PHONY: lint-isort
lint-isort:
	$(POETRY) run isort --check-only --diff eventsourcing

.PHONY: lint-mypy
lint-mypy:
	$(POETRY) run mypy eventsourcing


# .PHONY: lint-dockerfile
# lint-dockerfile:
# 	@docker run --rm -i replicated/dockerfilelint:ad65813 < ./dev/Dockerfile_eventsourcing_requirements
#

.PHONY: fmt
fmt: fmt-isort fmt-black

.PHONY: fmt-black
fmt-black:
	$(POETRY) run black eventsourcing

.PHONY: fmt-isort
fmt-isort:
	$(POETRY) run isort eventsourcing


.PHONY: test
test: coveragetest coverage100 timeit

.PHONY: coveragetest
coveragetest:
	$(POETRY) run coverage run -m unittest discover . -v

.PHONY: coverage100
coverage100:
	$(POETRY) run coverage report --fail-under=100 --show-missing

.PHONY: unittest
unittest:
	$(POETRY) run python -m unittest discover . -v



.PHONY: timeit
timeit: timeit_popo timeit_sqlite timeit_postgres

.PHONY: timeit_popo
timeit_popo:
	TEST_TIMEIT_FACTOR=500 $(POETRY) run python -m unittest eventsourcing.tests.application_tests.test_application_with_popo

.PHONY: timeit_sqlite
timeit_sqlite:
	TEST_TIMEIT_FACTOR=500 $(POETRY) run python -m unittest eventsourcing.tests.application_tests.test_application_with_sqlite

.PHONY: timeit_postgres
timeit_postgres:
	TEST_TIMEIT_FACTOR=500 $(POETRY) run python -m unittest eventsourcing.tests.application_tests.test_application_with_postgres

.PHONY: build
build:
	$(POETRY) build
# 	$(POETRY) build -f sdist    # build source distribution only

.PHONY: publish
publish:
	$(POETRY) publish

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


#
#
# .PHONY: coverage
# coverage: coveragetest coveragehtml coverage100
#
# .PHONY: prepush
# prepush: drop_postgres_db create_postgres_db updatetools lint docs test
#
# .PHONY: drop_postgres_db
# drop_postgres_db:
# 	dropdb eventsourcing
#
# .PHONY: create_postgres_db
# create_postgres_db:
# 	createdb eventsourcing
# 	psql eventsourcing -c "CREATE SCHEMA myschema AUTHORIZATION eventsourcing"
#
# .PHONY: updatetools
# updatetools:
# 	pip install -U pip
# 	pip install -U black mypy flake8 flake8-bugbear isort python-coveralls coverage orjson pydantic
#

.PHONY: docs
docs:
	cd docs && make html

#
# .PHONY: brew-services-start
# brew-services-start:
# #	brew services start mysql
# 	brew services start postgresql
# #	brew services start redis
# #	~/axonserver/axonserver.jar &
# #	cassandra -f &
#
#
# .PHONY: brew-services-stop
# brew-services-stop:
# #	brew services stop mysql || echo "Mysql couldn't be stopped"
# 	brew services stop postgresql || echo "PostgreSQL couldn't be stopped"
# #	brew services stop redis || echo "Redis couldn't be stopped"
# #	pkill -15 java
#
#
# .PHONY: prepare-dist
# prepare-dist:
# 	python ./dev/prepare-distribution.py
#
#
# .PHONY: release-dist
# release-dist:
# 	python ./dev/release-distribution.py
#
#
# .PHONY: test-released-distribution
# test-released-distribution:
# 	python ./dev/test-released-distribution.py
#
#
# .PHONY: ramdisk
# ramdisk:
# 	diskutil erasevolume HFS+ 'RAM Disk' `hdiutil attach -nobrowse -nomount ram://204800`
