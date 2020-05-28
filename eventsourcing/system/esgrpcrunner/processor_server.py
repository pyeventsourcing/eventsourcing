import logging
import traceback
from concurrent import futures
from json import JSONDecodeError
from queue import Queue
from signal import SIGINT, signal
from threading import Event, Lock, Thread
from time import sleep
from typing import Dict, Type

import grpc
from eventsourcing.application.notificationlog import (
    AbstractNotificationLog,
    LocalNotificationLog,
    NotificationLogReader,
    Section,
)
from eventsourcing.application.process import ProcessApplication
from eventsourcing.application.simple import (
    ApplicationWithConcreteInfrastructure,
    is_prompt_to_pull,
)
from eventsourcing.domain.model.events import subscribe
from eventsourcing.utils.topic import resolve_topic
from eventsourcing.utils.transcoding import ObjectJSONDecoder, ObjectJSONEncoder

from eventsourcing.system.esgrpcrunner.processor_client import ProcessorClient
from eventsourcing.system.esgrpcrunner.processor_pb2 import (
    CallReply,
    Empty,
    NotificationsReply,
)
from eventsourcing.system.esgrpcrunner.processor_pb2_grpc import (
    ProcessorServicer,
    add_ProcessorServicer_to_server,
)

from eventsourcing.application import notificationlog

notificationlog.USE_REGULAR_SECTIONS = False
notificationlog.DEFAULT_SECTION_SIZE = 100


class ProcessorServer(ProcessorServicer):
    def __init__(
        self,
        application_topic,
        infrastructure_topic,
        setup_table,
        address,
        upstreams,
        downstreams,
        push_prompt_interval,
    ):
        super(ProcessorServer, self).__init__()
        self.has_been_stopped = Event()
        signal(SIGINT, self.stop)
        self.application_class: Type[ProcessApplication] = resolve_topic(
            application_topic
        )
        self.application_name = self.application_class.create_name()
        infrastructure_class: Type[
            ApplicationWithConcreteInfrastructure
        ] = resolve_topic(infrastructure_topic)
        self.application = self.application_class.mixin(
            infrastructure_class=infrastructure_class
        )(setup_table=setup_table)
        self.address = address
        self.json_encoder = ObjectJSONEncoder()
        self.json_decoder = ObjectJSONDecoder()
        self.upstreams = upstreams
        self.downstreams = downstreams
        self.prompt_events = {}
        self.push_prompt_interval = push_prompt_interval

        self.notification_log_view = NotificationLogView(
            self.application.notification_log, json_encoder=ObjectJSONEncoder(),
        )
        for upstream_name in self.upstreams:
            self.prompt_events[upstream_name] = Event()
            # self.prompt_events[upstream_name].set()

        self.downstream_prompt_event = Event()
        subscribe(self._set_downstream_prompt_event, is_prompt_to_pull)

        self.serve()

        self.clients: Dict[str, ProcessorClient] = {}
        self.clients_lock = Lock()
        start_client_threads = []
        remotes = {}
        remotes.update(self.upstreams)
        remotes.update(self.downstreams)
        for name, address in remotes.items():
            thread = StartClient(self.clients, name, address)
            thread.setDaemon(True)
            thread.start()
            start_client_threads.append(thread)
        for thread in start_client_threads:
            thread.join()
            # logging.info("%s connected to %s" % (self.application_name, thread.name))

        self.push_prompts_thread = Thread(target=self._push_prompts)
        self.push_prompts_thread.setDaemon(True)
        self.push_prompts_thread.start()

        # self.count_of_events = 0

        self.pull_notifications_threads = {}
        self.unprocessed_domain_event_queue = Queue()
        for upstream_name, upstream_address in self.upstreams.items():
            thread = PullNotifications(
                prompt_event=self.prompt_events[upstream_name],
                reader=NotificationLogReader(
                    RemoteNotificationLog(
                        client=self.clients[upstream_name],
                        json_decoder=ObjectJSONDecoder(),
                        section_size=self.application.notification_log.section_size,
                    )
                ),
                process_application=self.application,
                event_queue=self.unprocessed_domain_event_queue,
                upstream_name=upstream_name,
                has_been_stopped=self.has_been_stopped,
            )
            thread.setDaemon(True)
            self.pull_notifications_threads[upstream_name] = thread

        self.process_events_thread = Thread(target=self._process_events)
        self.process_events_thread.setDaemon(True)
        self.process_events_thread.start()

        # Start the threads.
        for thread in self.pull_notifications_threads.values():
            thread.start()

        # Wait for termination.
        self.wait_for_termination()

    def _set_downstream_prompt_event(self, event):
        # logging.info(
        #     "Setting downstream prompt event on %s for %s"
        #     % (self.application_name, event)
        # )
        self.downstream_prompt_event.set()

    def _push_prompts(self) -> None:
        # logging.info("Started push prompts thread")
        while not self.has_been_stopped.is_set():
            try:
                self.__push_prompts()
                sleep(self.push_prompt_interval)
            except Exception as e:
                if not self.has_been_stopped.is_set():
                    logging.error(traceback.format_exc())
                    logging.error(
                        "Continuing after error in 'push prompts' thread: %s", e
                    )
                    sleep(1)

    def __push_prompts(self):
        self.downstream_prompt_event.wait()
        self.downstream_prompt_event.clear()
        # logging.info("Pushing prompts from %s" % self.application_name)
        for downstream_name in self.downstreams:
            client = self.clients[downstream_name]
            if not self.has_been_stopped.is_set():
                client.prompt(self.application_name)

    def _process_events(self) -> None:
        while not self.has_been_stopped.is_set():
            try:
                self.__process_events()
            except Exception as e:
                logging.error(traceback.format_exc())
                logging.error("Continuing after error in 'process events' thread:", e)
                sleep(1)

    def __process_events(self):
        unprocessed_item = self.unprocessed_domain_event_queue.get()
        self.unprocessed_domain_event_queue.task_done()
        if unprocessed_item is None:
            return
        else:
            # Process domain event.
            domain_event, notification_id, upstream_name = unprocessed_item
            # logging.info("Unprocessed event: %s" % domain_event)
            new_events, new_records = self.application.process_upstream_event(
                domain_event, notification_id, upstream_name
            )

            # Publish a prompt if there are new notifications.
            if any([event.__notifiable__ for event in new_events]):
                self.application.publish_prompt()

    def serve(self):
        self.executor = futures.ThreadPoolExecutor(max_workers=10)
        self.server = grpc.server(self.executor)
        # logging.info(self.application_class)
        add_ProcessorServicer_to_server(self, self.server)
        self.server.add_insecure_port(self.address)
        self.server.start()

    def wait_for_termination(self):
        self.server.wait_for_termination()

    def Ping(self, request, context):
        return Empty()

    def Follow(self, request, context):
        upstream_name = request.upstream_name
        upstream_address = request.upstream_address
        self.follow(upstream_name, upstream_address)
        return Empty()

    def follow(self, upstream_name, upstream_address):
        # logging.debug("%s is following %s" % (self.application_name, upstream_name))
        self.clients[upstream_name].lead(self.application_name, self.address)

    def Lead(self, request, context):
        downstream_name = request.downstream_name
        downstream_address = request.downstream_address
        self.lead(downstream_name, downstream_address)
        return Empty()

    def lead(self, downstream_name, downstream_address):
        # logging.debug("%s is leading %s" % (self.application_name, downstream_name))
        thread = StartClient(self.clients, downstream_name, downstream_address)
        thread.setDaemon(True)
        thread.start()
        thread.join()
        if thread.error:
            raise Exception(
                "Couldn't lead '%s' on address '%s': %s"
                % (downstream_name, downstream_address, thread.error)
            )
        else:
            self.downstreams[downstream_name] = downstream_address

    def start_client(self, name, address):
        if name not in self.clients:
            self.clients[name] = ProcessorClient()
            self.clients[name].connect(address)

    def Prompt(self, request, context):
        upstream_name = request.upstream_name
        self.prompt(upstream_name)
        return Empty()

    def prompt(self, upstream_name):
        # logging.info(
        #     "Application %s received prompt from %s"
        #     % (self.application_name, upstream_name)
        # )
        self.prompt_events[upstream_name].set()

    def GetNotifications(self, request, context):
        section_id = request.section_id
        section = self.get_notification_log_section(section_id)
        return NotificationsReply(section=section)

    def get_notification_log_section(self, section_id):
        return self.notification_log_view.present_resource(section_id=section_id)

    def CallApplicationMethod(self, request, context):
        method_name = request.method_name
        # logging.info("Call application method: %s" % method_name)
        args = self.json_decoder.decode(request.args)
        kwargs = self.json_decoder.decode(request.kwargs)
        method = getattr(self.application, method_name)
        return_value = method(*args, **kwargs)
        return CallReply(data=self.json_encoder.encode(return_value))

    def stop(self, *args):
        # logging.debug("Stopping....")
        self.has_been_stopped.set()
        self.server.stop(grace=1)


class PullNotifications(Thread):
    def __init__(
        self,
        prompt_event: Event,
        reader: NotificationLogReader,
        process_application: ProcessApplication,
        event_queue: Queue,
        upstream_name: str,
        has_been_stopped: Event,
    ):
        super(PullNotifications, self).__init__()
        self.prompt_event = prompt_event
        self.reader = reader
        self.process_application = process_application
        self.event_queue = event_queue
        self.upstream_name = upstream_name
        self.has_been_stopped = has_been_stopped

    def run(self) -> None:
        # logging.info("started pull notifications thread")
        self.set_reader_position()
        while not self.has_been_stopped.is_set():
            self.prompt_event.wait()
            self.prompt_event.clear()

            try:
                for notification in self.reader.read():
                    if self.has_been_stopped.is_set():
                        break
                    domain_event = self.process_application.get_event_from_notification(
                        notification
                    )
                    self.event_queue.put(
                        (domain_event, notification["id"], self.upstream_name)
                    )
            except Exception as e:
                logging.error(traceback.format_exc(e))
                logging.error("Error reading notification log: %s" % e)
                logging.error("Retrying...")
                self.set_reader_position()
                sleep(1)

    def set_reader_position(self):
        recorded_position = self.process_application.get_recorded_position(
            self.upstream_name
        )
        self.reader.seek(recorded_position)


class StartClient(Thread):
    def __init__(self, clients, name, address):
        super(StartClient, self).__init__()
        self.clients = clients
        self.name = name
        self.address = address
        self.error = None

    def run(self):
        client = ProcessorClient()
        try:
            client.connect(self.address)
        except Exception as e:
            self.error = e
            logging.error(e)
        else:
            self.clients[self.name] = client


class RemoteNotificationLog(AbstractNotificationLog):
    def __init__(
        self,
        client: ProcessorClient,
        json_decoder: ObjectJSONDecoder,
        section_size: int,
    ):
        self.client = client
        self.json_decoder = json_decoder
        self._section_size = section_size

    @property
    def section_size(self) -> int:
        return self._section_size

    def __getitem__(self, section_id: str) -> Section:
        section = self.client.get_notifications(section_id)
        try:
            obj = self.json_decoder.decode(section)
        except JSONDecodeError:
            raise ValueError("Couldn't decode section: %s" % section)
        return Section(**obj)


class NotificationLogView(object):
    def __init__(
        self, notification_log: LocalNotificationLog, json_encoder: ObjectJSONEncoder
    ):
        self.notification_log = notification_log
        self.json_encoder = json_encoder

    def present_resource(self, section_id: str) -> bytes:
        section = self.notification_log[section_id]
        return self.json_encoder.encode(section.__dict__)
