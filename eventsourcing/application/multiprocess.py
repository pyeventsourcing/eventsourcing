import multiprocessing
from multiprocessing import Manager
from time import sleep

import six

from eventsourcing.application.process import Prompt
from eventsourcing.application.system import System
from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.events import subscribe, unsubscribe
from eventsourcing.exceptions import CausalDependencyFailed
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.interface.notificationlog import RecordManagerNotificationLog
from eventsourcing.utils.uuids import uuid_from_application_name

DEFAULT_POLL_INTERVAL = 5


class Multiprocess(object):

    def __init__(self, system, pipeline_ids=(-1,), poll_interval=None, notification_log_section_size=5,
                 pool_size=1):
        self.pool_size = pool_size
        self.system = system
        self.pipeline_ids = pipeline_ids
        self.poll_interval = poll_interval or DEFAULT_POLL_INTERVAL
        assert isinstance(system, System)
        self.os_processes = None
        self.notification_log_section_size = notification_log_section_size

    def start(self):
        assert self.os_processes is None, "Already started"

        self.os_processes = []

        self.manager = Manager()
        self.inboxes = {}
        self.outboxes = {}

        # Setup queues.
        for pipeline_id in self.pipeline_ids:
            for process_class, upstream_classes in self.system.followings.items():
                inbox_id = (pipeline_id, process_class.__name__.lower())
                if inbox_id not in self.inboxes:
                    self.inboxes[inbox_id] = self.manager.Queue()
                for upstream_class in upstream_classes:
                    outbox_id = (pipeline_id, upstream_class.__name__.lower())
                    if outbox_id not in self.outboxes:
                        self.outboxes[outbox_id] = Outbox()
                    if inbox_id not in self.outboxes[outbox_id].downstream_inboxes:
                        self.outboxes[outbox_id].downstream_inboxes[inbox_id] = self.inboxes[inbox_id]

        # Subscribe to broadcast prompts published by a process
        # application in the parent operating system process.
        subscribe(handler=self.broadcast_prompt, predicate=self.is_prompt)

        # Start operating system process.
        for pipeline_id in self.pipeline_ids:
            for process_class, upstream_classes in self.system.followings.items():
                os_process = OperatingSystemProcess(
                    application_process_class=process_class,
                    upstream_names=[cls.__name__.lower() for cls in upstream_classes],
                    poll_interval=self.poll_interval,
                    pipeline_id=pipeline_id,
                    notification_log_section_size=self.notification_log_section_size,
                    pool_size=self.pool_size,
                    inbox=self.inboxes[(pipeline_id, process_class.__name__.lower())],
                    outbox=self.outboxes[(pipeline_id, process_class.__name__.lower())],
                )
                os_process.daemon = True
                os_process.start()
                self.os_processes.append(os_process)
                sleep(0.1)

    def broadcast_prompt(self, prompt):
        outbox_id = (prompt.pipeline_id, prompt.process_name)
        assert outbox_id in self.outboxes, (outbox_id, self.outboxes.keys())
        self.outboxes[outbox_id].put(prompt)

    @staticmethod
    def is_prompt(event):
        return isinstance(event, Prompt)

    def close(self):
        unsubscribe(handler=self.broadcast_prompt, predicate=self.is_prompt)

        for os_process in self.os_processes:
            os_process.inbox.put('QUIT')

        for os_process in self.os_processes:
            os_process.join(timeout=10)

        for os_process in self.os_processes:
            os_process.is_alive() and os_process.terminate()

        self.os_processes = None
        self.manager = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class Outbox(object):
    def __init__(self):
        self.downstream_inboxes = {}

    def put(self, msg):
        for q in self.downstream_inboxes.values():
            q.put(msg)


class OperatingSystemProcess(multiprocessing.Process):

    def __init__(self, application_process_class, upstream_names, pipeline_id=-1,
                 poll_interval=DEFAULT_POLL_INTERVAL, notification_log_section_size=None,
                 pool_size=5, inbox=None, outbox=None, *args, **kwargs):
        super(OperatingSystemProcess, self).__init__(*args, **kwargs)
        self.application_process_class = application_process_class
        self.upstream_names = upstream_names
        self.daemon = True
        self.pipeline_id = pipeline_id
        self.poll_interval = poll_interval
        self.notification_log_section_size = notification_log_section_size
        self.pool_size = pool_size
        self.inbox = inbox
        self.outbox = outbox

    def run(self):
        # Construct process application object.
        self.process = self.application_process_class(
            pipeline_id=self.pipeline_id,
            notification_log_section_size=self.notification_log_section_size,
            pool_size=self.pool_size,
        )

        # Follow upstream notification logs.
        for upstream_name in self.upstream_names:

            # Obtain a notification log object (local or remote) for the upstream process.
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
                upstream_application_id = uuid_from_application_name(upstream_name)
                notification_log = RecordManagerNotificationLog(
                    record_manager=type(record_manager)(
                        session=record_manager.session,
                        record_class=record_manager.record_class,
                        contiguous_record_ids=record_manager.contiguous_record_ids,
                        sequenced_item_class=record_manager.sequenced_item_class,
                        application_id=upstream_application_id,
                        pipeline_id=self.pipeline_id
                    ),
                    section_size=self.process.notification_log_section_size
                )
                # Todo: Support upstream partition IDs different from self.pipeline_id.
                # Todo: Support combining partitions. Read from different partitions but write to the same partition,
                # could be one os process that reads from many logs of the same upstream app, or many processes each
                # reading one partition with contention writing to the same partition).
                # Todo: Support dividing partitions Read from one but write to many. Maybe one process per
                # upstream partition, round-robin to pick partition for write. Or have many processes reading
                # with each taking it in turn to skip processing somehow.
                # Todo: Dividing partitions would allow a stream to flow at the same rate through slower
                # process applications.
                # Todo: Support merging results from "replicated state machines" - could have a command
                # logging process that takes client commands and presents them in a notification log.
                # Then the system could be deployed in different places, running independently, receiving
                # the same commands, and running the same processes. The command logging process could
                # be accompanied with a result logging process that reads results from replicas as they
                # are available. Not sure what to do if replicas return different things. If one replica
                # goes down, then it could resume by pulling events from another? Not sure what to do.
                # External systems could be modelled as commands.

            # Make the process follow the upstream notification log.
            self.process.follow(upstream_name, notification_log)

        # Subscribe to broadcast prompts published by the process application.
        subscribe(handler=self.broadcast_prompt, predicate=self.is_prompt)

        try:
            self.loop_on_prompts()
        finally:
            unsubscribe(handler=self.broadcast_prompt, predicate=self.is_prompt)

    @retry(CausalDependencyFailed, max_attempts=100, wait=0.1)
    def loop_on_prompts(self):

        # Run once, in case prompts were missed.
        self.process.run()

        # Loop on getting prompts.
        while True:
            try:
                # Todo: Make the poll interval gradually increase if there are only timeouts?
                item = self.inbox.get(timeout=self.poll_interval)
                self.inbox.task_done()

                if item == 'QUIT':
                    self.process.close()
                    break

                else:
                    self.process.run(item)

            except six.moves.queue.Empty:
                # Basically, we're polling after a timeout.
                self.process.run()

    def broadcast_prompt(self, prompt):
        self.outbox.put(prompt)

    @staticmethod
    def is_prompt(event):
        return isinstance(event, Prompt)
