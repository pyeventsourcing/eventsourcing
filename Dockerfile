FROM python:3.6

WORKDIR /app

RUN mkdir eventsourcing
COPY setup.py /app/setup.py
COPY eventsourcing/__init__.py /app/eventsourcing/
RUN pip install -e .[testing]
RUN pip uninstall eventsourcing --yes
RUN rm -rf /app/eventsourcing
