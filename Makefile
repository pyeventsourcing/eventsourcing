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


.PHONY: quick-test
quick-test:
	QUICK_TESTS_ONLY=1 python -m unittest discover eventsourcing.tests -vv


.PHONY: docs
docs:
	cd docs && make html


.PHONY: brew-services-start
brew-services-start:
	brew services start mysql
	brew services start postgresql
	brew services start redis
	~/axonserver/axonserver.jar &
	cassandra -f &


.PHONY: brew-services-stop
brew-services-stop:
	brew services stop mysql || echo "Mysql couldn't be stopped"
	brew services stop postgresql || echo "PostgreSQL couldn't be stopped"
	brew services stop redis || echo "Redis couldn't be stopped"
	pkill -15 java


.PHONY: prepare-distribution
prepare-distribution:
	python ./dev/prepare-distribution.py


.PHONY: release-distribution
release-distribution:
	python ./dev/release-distribution.py


.PHONY: test-released-distribution
test-released-distribution:
	python ./dev/test-released-distribution.py

.PHONY: generate-grpc-protos
generate-grpc-protos:
	python -m grpc_tools.protoc \
	  --proto_path=./eventsourcing/system/grpc \
	  --python_out=eventsourcing/system/grpc \
	  --grpc_python_out=eventsourcing/system/grpc \
	  eventsourcing/system/grpc/processor.proto
