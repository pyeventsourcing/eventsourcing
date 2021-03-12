.EXPORT_ALL_VARIABLES:
DOTENV_FILE ?= dev/.env

-include $(DOTENV_FILE)

.PHONY: install
install:
	@pip install -e ".[dev]"

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
	@black --check --diff eventsourcing
	@black --check --diff setup.py

.PHONY: lint-flake8
lint-flake8:
	@flake8 eventsourcing

.PHONY: lint-isort
lint-isort:
	@isort --check-only --diff eventsourcing

.PHONY: lint-mypy
lint-mypy:
	@mypy eventsourcing

.PHONY: lint-dockerfile
lint-dockerfile:
	@docker run --rm -i replicated/dockerfilelint:ad65813 < ./dev/Dockerfile_eventsourcing_requirements

.PHONY: lint
lint: lint-isort lint-black lint-flake8 lint-mypy #lint-dockerfile


.PHONY: fmt-isort
fmt-isort:
	@isort eventsourcing

.PHONY: fmt-black
fmt-black:
	@black eventsourcing
	@black setup.py

.PHONY: fmt
fmt: fmt-isort fmt-black

.PHONY: unittest
unittest:
	@python -m unittest discover eventsourcing -v

.PHONY: timeit
timeit:
	TEST_TIMEIT_FACTOR=500 python -m unittest eventsourcing.tests.test_application

.PHONY: coveragetest
coveragetest:
	@coverage run -m unittest discover eventsourcing -v
#	@coverage run \
#		--concurrency=multiprocessing \
#		-m unittest discover \
		eventsourcing -vv --failfast
#	@coverage combine
#	@coverage report
#	@coverage html

.PHONY: coverage100
coverage100:
	@coverage report --fail-under=100

.PHONY: coveragehtml
coveragehtml:
	@coverage html

.PHONY: test
test: coveragetest coverage100 timeit

.PHONY: coverage
coverage: coveragetest coveragehtml coverage100

.PHONY: prepush
prepush: lint docs test

.PHONY: docs
docs:
	cd docs && make html


.PHONY: brew-services-start
brew-services-start:
#	brew services start mysql
	brew services start postgresql
#	brew services start redis
#	~/axonserver/axonserver.jar &
#	cassandra -f &


.PHONY: brew-services-stop
brew-services-stop:
#	brew services stop mysql || echo "Mysql couldn't be stopped"
	brew services stop postgresql || echo "PostgreSQL couldn't be stopped"
#	brew services stop redis || echo "Redis couldn't be stopped"
#	pkill -15 java


.PHONY: prepare-dist
prepare-dist:
	python ./dev/prepare-distribution.py


.PHONY: release-dist
release-dist:
	python ./dev/release-distribution.py


.PHONY: test-released-distribution
test-released-distribution:
	python ./dev/test-released-distribution.py

#.PHONY: generate-grpc-protos
#generate-grpc-protos:
#	python -m grpc_tools.protoc \
#	  --proto_path=./eventsourcing/system/grpc \
#	  --python_out=eventsourcing/system/grpc \
#	  --grpc_python_out=eventsourcing/system/grpc \
#	  eventsourcing/system/grpc/processor.proto

.PHONY: ramdisk
ramdisk:
	diskutil erasevolume HFS+ 'RAM Disk' `hdiutil attach -nobrowse -nomount ram://204800`
