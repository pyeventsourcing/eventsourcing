import multiprocessing

import redis
import time

import six

from eventsourcing.application.process import Process, Prompt
from eventsourcing.domain.model.events import subscribe, unsubscribe


class OperatingSystemProcess(multiprocessing.Process):

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
        self.process = Process(
            self.process_name,
            policy=self.process_policy,
            persist_event_type=self.process_persist_event_type,
            setup_table=False,
        )

        # Follow upstream notification logs.
        for upstream_name in self.upstream_names:
            self.process.follow(upstream_name, self.process.notification_log)

            # Subscribe to prompts from upstream channels.
            self.pubsub.subscribe(upstream_name)

        subscribe(handler=self.broadcast_prompt, predicate=self.is_prompt)
        try:
            self.run_loop_with_subscription()
            # self.run_loop_with_sleep()
        finally:
            unsubscribe(handler=self.broadcast_prompt, predicate=self.is_prompt)

    def run_loop_with_subscription(self):
        while True:
            item = self.pubsub.get_message()
            # print("Pubsub message: {}".format(item))
            if item is None:
                continue
            elif item['type'] in ['subscribe', 'unsubscribe']:
                continue
            elif item['type'] == 'message':
                # raise Exception(item)

                if item['data'] == b"KILL":
                    self.pubsub.unsubscribe()
                    break
                else:
                    # try:
                    #     expected_position = int(item['data'])
                    # except ValueError as e:
                    #     raise Exception("{}: {}".format(e, item))
                    # assert isinstance(expected_position, six.integer_types)
                    # Sometimes the prompt arrives before the data is visible in the database.
                    count_tries = 0
                    max_tries = 20
                    upstream_application_name = item['channel'].decode('utf8')
                    prompt = Prompt(upstream_application_name)

                    while count_tries < max_tries:
                        # if self.process.run(prompt):
                        if self.process.run(prompt):
                            break
                            # tracking_end_position = self.process.tracking_record_manager.get_max_record_id(
                            #     self.process.name, upstream_application_name
                            # )
                            # if tracking_end_position >= expected_position:
                            #     time.sleep(0.05)
                            #     self.process.run()
                            #     break

                        count_tries += 1
                        time.sleep(0.05 * count_tries)

                    # Todo: Check the reader position reflect the
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
