# To use this Docker file in PyCharm, just add a new Docker project interpreter,
# and set an image name such as "eventsourcing_requirements:latest". It will
# take a little while to download and build everything, but then tests which
# do not depend on other services such as MySQL and Cassandra should pass.
# To run containers needed to pass the full test suite, see docker-compose.yaml.
FROM python:3.6

WORKDIR /app

RUN mkdir eventsourcing
COPY setup.py /app/setup.py
COPY eventsourcing/__init__.py /app/eventsourcing/
RUN pip install -e .[testing]
RUN pip uninstall eventsourcing --yes
RUN rm -rf /app/eventsourcing
