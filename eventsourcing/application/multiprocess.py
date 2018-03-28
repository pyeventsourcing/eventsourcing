import multiprocessing
from time import sleep

import redis

from eventsourcing.application.process import Prompt, System, make_channel_name
from eventsourcing.application.simple import DEFAULT_PIPELINE_ID
from eventsourcing.domain.model.events import subscribe, unsubscribe
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.interface.notificationlog import RecordManagerNotificationLog
from eventsourcing.utils.uuids import uuid_from_application_name


DEFAULT_POLL_INTERVAL = 5


class OperatingSystemProcess(multiprocessing.Process):

    def __init__(self, application_process_class, upstream_names, pipeline_id=None,
                 poll_interval=DEFAULT_POLL_INTERVAL, notification_log_section_size=None,
                 pool_size=5, *args, **kwargs):
        super(OperatingSystemProcess, self).__init__(*args, **kwargs)
        self.application_process_class = application_process_class
        self.upstream_names = upstream_names
        self.daemon = True
        self.pipeline_id = pipeline_id
        self.poll_interval = poll_interval
        self.notification_log_section_size = notification_log_section_size
        self.pool_size = pool_size

    def run(self):
        self.redis = redis.Redis()
        self.pubsub = self.redis.pubsub()

        # Construct process application.
        self.process = self.application_process_class(
            pipeline_id=self.pipeline_id,
            notification_log_section_size=self.notification_log_section_size,
            pool_size=self.pool_size,
        )

        # Follow upstream notification logs.
        for upstream_name in self.upstream_names:

            # Subscribe to prompts from upstream partition.
            channel_name = make_channel_name(
                application_name=upstream_name,
                pipeline_id=self.pipeline_id
            )
            self.pubsub.subscribe(channel_name)

            # Obtain a notification log for the upstream process.
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

        # Run a loop.
        try:
            while True:
                try:
                    self.loop_on_prompts()
                    # self.run_loop_with_sleep()
                except Exception as e:
                    # Todo: Log this, or stderr?
                    print("Caught exception: {}".format(e))
                    raise e
                else:
                    break

        finally:
            unsubscribe(handler=self.broadcast_prompt, predicate=self.is_prompt)

    def loop_on_prompts(self):

        # Run once, in case prompts were missed.
        self.process.run()

        # Loop on getting prompts.
        while True:
            # Note, get_message() returns immediately with None if timeout=0.
            item = self.pubsub.get_message(timeout=self.poll_interval)
            # Todo: Make the poll interval gradually increase if there only timeouts?
            if item is None:
                # Basically, we're polling after each timeout interval.
                self.process.run()
            elif item['type'] == 'message':
                # Identify message, and take appropriate action.
                if item['data'] == b"QUIT":
                    self.pubsub.unsubscribe()
                    self.process.close()
                    break
                else:
                    # Pull from upstream.
                    channel_name = item['channel'].decode('utf8')
                    prompt = Prompt(channel_name)

                    self.process.run(prompt)

                    # Todo: Check the reader position reflects the prompt notification ID? Skip if done.
                    # Todo: Replace above sleep with check the prompted notification is available (otherwise repeat).
                    # Todo: Put the notification ID in the prompt?
                    # Todo: Put the whole notification in the prompt, so if it's the only thing we don't have,
                    # it can be processed.

            elif item['type'] == 'subscribe':
                pass
            elif item['type'] == 'unsubscribe':
                pass

            else:
                raise Exception(item)

    def broadcast_prompt(self, prompt):
        assert isinstance(prompt, Prompt)
        self.redis.publish(prompt.channel_name, prompt.end_position)

    @staticmethod
    def is_prompt(event):
        return isinstance(event, Prompt)


    # def run_loop_with_sleep(self):
    #     while True:
    #         self.process.run()
    #         time.sleep(.1)


class Multiprocess(object):

    def __init__(self, system, pipeline_ids=None, poll_interval=None, notification_log_section_size=5,
                 pool_size=1):
        self.pool_size = pool_size
        self.system = system
        # if pipeline_ids is None:
        #     pipeline_ids = [uuid4()]
        self.pipeline_ids = pipeline_ids or [DEFAULT_PIPELINE_ID]
        self.poll_interval = poll_interval or DEFAULT_POLL_INTERVAL
        assert isinstance(system, System)
        self.os_processes = None
        self.notification_log_section_size = notification_log_section_size

    def start(self):
        assert self.os_processes is None, "Already started"
        self.redis = redis.Redis()

        self.os_processes = []

        for process_class, upstream_classes in self.system.followings.items():

            for pipeline_id in self.pipeline_ids:
                # Start operating system process.
                os_process = OperatingSystemProcess(
                    application_process_class=process_class,
                    upstream_names=[cls.__name__.lower() for cls in upstream_classes],
                    poll_interval=self.poll_interval,
                    pipeline_id=pipeline_id,
                    notification_log_section_size=self.notification_log_section_size,
                    pool_size=self.pool_size,
                )
                os_process.start()
                self.os_processes.append(os_process)

    def prompt_about(self, process_name, pipeline_id):
        for process_class in self.system.process_classes:

            name = process_class.__name__.lower()

            if process_name and process_name != name:
                continue

            num_expected_subscriptions = len(self.system.followings[process_class])
            channel_name = make_channel_name(name, pipeline_id)
            patience = 50
            while self.redis.publish(channel_name, '') < num_expected_subscriptions:
                if patience:
                    patience -= 1
                    sleep(0.01)  # How long does it take to subscribe?
                else:
                    raise Exception("Couldn't publish to expected number of subscribers "
                                    "({}, {})".format(name, num_expected_subscriptions))

            sleep(0.001)

    def close(self):
        for os_process in self.os_processes:
            for pipeline_id in self.pipeline_ids:
                name = os_process.application_process_class.__name__.lower()
                channel_name = make_channel_name(name, pipeline_id)
                self.redis.publish(channel_name, 'QUIT')

        for os_process in self.os_processes:
            os_process.join(timeout=10)

        for os_process in self.os_processes:
            if os_process.is_alive():
                os_process.terminate()

        self.os_processes = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

