import json
import logging
import subprocess
import sys
from concurrent import futures
from signal import SIGINT
from subprocess import Popen, TimeoutExpired
from threading import Event
from typing import List, Type

import grpc

from eventsourcing.application.popo import PopoApplication
from eventsourcing.infrastructure.base import DEFAULT_PIPELINE_ID
from eventsourcing.system.definition import AbstractSystemRunner, TProcessApplication
from eventsourcing.system.grpc import processor
from eventsourcing.system.grpc.processor import ProcessorClient
from eventsourcing.system.grpc.processor_pb2 import Empty
from eventsourcing.system.grpc.processor_pb2_grpc import (
    ProcessorServicer,
    add_ProcessorServicer_to_server,
)
from eventsourcing.utils.topic import get_topic

logging.basicConfig()


class GrpcRunner(AbstractSystemRunner):
    """
    System runner that uses gRPC to communicate between process applications.
    """

    def __init__(
        self,
        *args,
        pipeline_ids=(DEFAULT_PIPELINE_ID,),
        push_prompt_interval=0.25,
        **kwargs
    ):
        super(GrpcRunner, self).__init__(*args, **kwargs)
        self.push_prompt_interval = push_prompt_interval
        self.pipeline_ids = pipeline_ids
        self.processors: List[Popen] = []
        self.addresses = {}
        self.port_generator = self.generate_ports(start=50051)

    def generate_ports(self, start: int):
        """
        Generator that yields a sequence of ports from given start number.
        """
        i = 0
        while True:
            yield start + i
            i += 1

    def create_address(self):
        """
        Creates a new address for a gRPC server.
        """
        return "localhost:%s" % next(self.port_generator)

    def start(self):
        """
        Starts running a system of process applications.
        """
        for i, application_name in enumerate(self.system.process_classes):
            for pipeline_id in self.pipeline_ids:
                self.addresses[(application_name, pipeline_id)] = self.create_address()

        # Start the processors.
        for (application_name, pipeline_id), address in self.addresses.items():
            application_topic = get_topic(self.system.process_classes[application_name])
            infrastructure_topic = get_topic(
                self.infrastructure_class or PopoApplication
            )
            upstreams = {}
            for upstream_name in self.system.upstream_names[application_name]:
                upstreams[upstream_name] = self.addresses[(upstream_name, pipeline_id)]
            downstreams = {}
            for downstream_name in self.system.downstream_names[application_name]:
                downstreams[downstream_name] = self.addresses[(downstream_name,
                                                               pipeline_id)]
            self.start_processor(
                application_topic,
                pipeline_id,
                infrastructure_topic,
                self.setup_tables,
                address,
                upstreams,
                downstreams,
            )

    def start_processor(
        self,
        application_topic,
        pipeline_id,
        infrastructure_topic,
        setup_table,
        address,
        upstreams,
        downstreams,
    ):
        """
        Starts a gRPC process.
        """
        # os.environ["DB_URI"] = (
        #     "mysql+pymysql://{}:{}@{}/eventsourcing{
        #     }?charset=utf8mb4&binary_prefix=true"
        # ).format(
        #     os.getenv("MYSQL_USER", "eventsourcing"),
        #     os.getenv("MYSQL_PASSWORD", "eventsourcing"),
        #     os.getenv("MYSQL_HOST", "127.0.0.1"),
        #     resolve_topic(application_topic).create_name()
        #     if self.use_individual_databases
        #     else "",
        # )

        process = Popen(
            [
                sys.executable,
                processor.__file__,
                application_topic,
                json.dumps(pipeline_id),
                infrastructure_topic,
                json.dumps(setup_table),
                address,
                json.dumps(upstreams),
                json.dumps(downstreams),
                json.dumps(self.push_prompt_interval),
            ],
            stderr=subprocess.STDOUT,
            close_fds=True,
        )
        self.processors.append(process)

    def close(self) -> None:
        """
        Stops all gRPC processes started by the runner.
        """
        for process in self.processors:
            self.stop_process(process)
        for process in self.processors:
            self.kill_process(process)

    def stop_process(self, process):
        """
        Stops given gRPC process.
        """
        exit_status_code = process.poll()
        if exit_status_code is None:
            process.send_signal(SIGINT)

    def kill_process(self, process):
        """
        Kills given gRPC process, if it still running.
        """
        try:
            process.wait(timeout=1)
        except TimeoutExpired:
            print("Timed out waiting for process to stop. Terminating....")
            process.terminate()
            try:
                process.wait(timeout=1)
            except TimeoutExpired:
                print("Timed out waiting for process to terminate. Killing....")
                process.kill()
            print("Processor exit code: %s" % process.poll())

    def _construct_app_by_class(
        self, process_class: Type[TProcessApplication], pipeline_id: int
    ) -> TProcessApplication:
        client = ProcessorClient()
        client.connect(self.addresses[(process_class.create_name(), pipeline_id)])
        return ClientWrapper(client)

    def listen(self, name, processor_clients):
        """
        Constructs a listener using the given clients.
        """
        processor_clients: List[ProcessorClient]
        return ProcessorListener(
            name=name, address=self.create_address(), clients=processor_clients
        )


class ClientWrapper:
    """
    Wraps a gRPC client, and returns a MethodWrapper when attributes are accessed.
    """

    def __init__(self, client: ProcessorClient):
        self.client = client

    def __getattr__(self, item):
        return MethodWrapper(self.client, item)


class MethodWrapper:
    """
    Wraps a gRPC client, and invokes application method name when called.
    """

    def __init__(self, client: ProcessorClient, method_name: str):
        self.client = client
        self.method_name = method_name

    def __call__(self, *args, **kwargs):
        return self.client.call_application(self.method_name, *args, **kwargs)


class ProcessorListener(ProcessorServicer):
    """
    Starts server and uses clients to request prompts from connected servers.
    """

    def __init__(self, name, address, clients: List[ProcessorClient]):
        super().__init__()
        self.name = name
        self.address = address
        self.clients = clients
        self.prompt_events = {}
        self.pull_notification_threads = {}
        self.serve()
        for client in self.clients:
            client.lead(self.name, self.address)

    def serve(self):
        """
        Starts server.
        """
        self.executor = futures.ThreadPoolExecutor(max_workers=10)
        self.server = grpc.server(self.executor)
        add_ProcessorServicer_to_server(self, self.server)
        self.server.add_insecure_port(self.address)
        self.server.start()

    def Ping(self, request, context):
        return Empty()

    def Prompt(self, request, context):
        upstream_name = request.upstream_name
        self.prompt(upstream_name)
        return Empty()

    def prompt(self, upstream_name):
        """
        Sets prompt events for given upstream process.
        """
        # logging.info(
        #     "Application %s received prompt from %s"
        #     % (self.application_name, upstream_name)
        # )
        if upstream_name not in self.prompt_events:
            self.prompt_events[upstream_name] = Event()
        self.prompt_events[upstream_name].set()
