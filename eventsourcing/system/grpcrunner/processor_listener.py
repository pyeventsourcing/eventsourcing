from concurrent import futures
from threading import Event
from typing import List

import grpc

from eventsourcing.system.grpcrunner.processor_client import ProcessorClient
from eventsourcing.system.grpcrunner.processor_pb2 import Empty
from eventsourcing.system.grpcrunner.processor_pb2_grpc import (
    ProcessorServicer,
    add_ProcessorServicer_to_server,
)


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
