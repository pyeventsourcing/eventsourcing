FROM python:3.6

WORKDIR /app

RUN mkdir eventsourcing
COPY setup.py /app/setup.py
COPY eventsourcing/__init__.py /app/eventsourcing/
RUN pip install -e .[testing]
RUN rm -rf /app/eventsourcing/*

# Now copy in our code, and run it
COPY eventsourcing/* /app/eventsourcing/

#EXPOSE 8000
#CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
# Now copy in our code, and run it
