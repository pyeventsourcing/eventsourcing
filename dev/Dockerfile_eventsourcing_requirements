FROM python:3.7

WORKDIR /app

# Copy enough to install the eventsourcing requirements.
COPY setup.py /app/setup.py
RUN mkdir eventsourcing
COPY eventsourcing/ /app/eventsourcing/

# Install the requirements.
RUN pip install -e .[testing]

# Remove the package source files.
RUN pip uninstall eventsourcing --yes
RUN rm -rf /app/eventsourcing
