import multiprocessing
import time

import redis

from eventsourcing.application.process import Process, Prompt
from eventsourcing.domain.model.events import subscribe, unsubscribe
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.interface.notificationlog import RecordManagerNotificationLog
from eventsourcing.utils.uuids import uuid_from_application_name


class OperatingSystemProcess(multiprocessing.Process):
    application_process_class = Process

    def __init__(self, process_name, process_policy, process_persist_event_type, upstream_names, *args, **kwargs):
        super(OperatingSystemProcess, self).__init__(*args, **kwargs)

        self.process_name = process_name
        self.process_policy = process_policy
        self.process_persist_event_type = process_persist_event_type
        self.upstream_names = upstream_names
        self.daemon = True

    # Configure to publish prompts to Redis.
    def broadcast_prompt(self, event):
        self.redis.publish(event.sender_process_name, event.end_position)

    @staticmethod
    def is_prompt(event):
        return isinstance(event, Prompt)

    def run(self):
        self.redis = redis.Redis()
        self.pubsub = self.redis.pubsub()

        # Construct process.
        self.process = self.application_process_class(
            self.process_name,
            policy=self.process_policy,
            persist_event_type=self.process_persist_event_type,
            setup_table=False,
        )

        # Follow upstream notification logs.
        for upstream_name in self.upstream_names:
            if upstream_name == self.process.name:
                # Upstream is this process's application,
                # so use own notification log.
                notification_log = self.process.notification_log
            else:
                # For a different application, we need to construct a notification
                # log with a record manager that has the upstream application ID.
                # Currently assumes all applications are using the same database
                # and record manager class. If it wasn't the same database,we would
                # to use a remote notification log, and upstream would need to provide
                # an API from which we can pull. It's not unreasonable to have a fixed
                # number of application processes connecting to the same database.
                record_manager = self.process.event_store.record_manager
                assert isinstance(record_manager, SQLAlchemyRecordManager)
                application_id = uuid_from_application_name(upstream_name)
                notification_log = RecordManagerNotificationLog(
                    record_manager=type(record_manager)(
                        session=record_manager.session,
                        record_class=record_manager.record_class,
                        contiguous_record_ids=record_manager.contiguous_record_ids,
                        sequenced_item_class=record_manager.sequenced_item_class,
                        application_id=application_id
                    ),
                    section_size=self.process.notification_log.section_size
                )

            # Configure to follow the upstream notification log.
            self.process.follow(upstream_name, notification_log)

            # Subscribe to prompts from upstream channels.
            self.pubsub.subscribe(upstream_name)

        # Loop.
        subscribe(handler=self.broadcast_prompt, predicate=self.is_prompt)
        try:
            self.run_loop_with_subscription()
            # self.run_loop_with_sleep()

        finally:
            unsubscribe(handler=self.broadcast_prompt, predicate=self.is_prompt)

    def run_loop_with_subscription(self):
        while True:
            # Note, get_message() returns immediately with None if timeout == 0.
            item = self.pubsub.get_message(timeout=10, ignore_subscribe_messages=True)
            if item is None:
                # Bascially, we're polling after each timeout interval.
                self.process.run()
            elif item['type'] == 'message':
                # Identify message, and take appropriate action.
                if item['data'] == b"KILL":
                    # Shutdown.
                    self.pubsub.unsubscribe()
                    self.process.close()
                    break
                else:
                    # Pull from upstream.
                    upstream_application_name = item['channel'].decode('utf8')
                    prompt = Prompt(upstream_application_name)
                    if not self.process.run(prompt):
                        # Have another go.
                        time.sleep(0.01)
                        self.process.run(prompt)

                    # Todo: Check the reader position reflect the prompt notification ID.
                    # Todo: Replace above sleep with check the prompted notification is available (otherwise repeat).
                    # Todo: Put the notification ID in the prompt?
                    # Todo: Put the whole notification in the prompt, so if it's the only thing we don't have,
                    # it can be processed.
            else:
                raise Exception(item)

    def run_loop_with_sleep(self):
        while True:
            if self.process.run():
                time.sleep(.1)
            else:
                time.sleep(1)
