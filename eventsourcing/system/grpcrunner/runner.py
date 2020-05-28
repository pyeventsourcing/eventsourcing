import json
import logging
import os
import subprocess
import sys
from signal import SIGINT
from subprocess import Popen, TimeoutExpired
from typing import List, Type

from eventsourcing.application.popo import PopoApplication
from eventsourcing.system.definition import AbstractSystemRunner, TProcessApplication
from eventsourcing.system.grpcrunner import processor
from eventsourcing.utils.topic import get_topic, resolve_topic

from eventsourcing.system.grpcrunner.processor_client import ProcessorClient
from eventsourcing.system.grpcrunner.processor_listener import ProcessorListener

logging.basicConfig()


class GrpcRunner(AbstractSystemRunner):
    """
    System runner that uses gRPC to communicate between process applications.
    """
    def __init__(
        self, *args, push_prompt_interval=0.25, use_individual_databases=False, **kwargs
    ):
        super(GrpcRunner, self).__init__(*args, **kwargs)
        self.processors: List[Popen] = []
        self.addresses = {}
        self.port_generator = self.generate_ports(start=50051)
        self.push_prompt_interval = push_prompt_interval
        self.use_individual_databases = use_individual_databases

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
        return "[::]:%s" % next(self.port_generator)

    def start(self):
        """
        Starts running a system of process applications.
        """
        for i, application_name in enumerate(self.system.process_classes):
            self.addresses[application_name] = self.create_address()

        # Start the processors.
        for application_name, address in self.addresses.items():
            application_topic = get_topic(self.system.process_classes[application_name])
            infrastructure_topic = get_topic(
                self.infrastructure_class or PopoApplication
            )
            upstreams = {}
            for upstream_name in self.system.upstream_names[application_name]:
                upstreams[upstream_name] = self.addresses[upstream_name]
            downstreams = {}
            for downstream_name in self.system.downstream_names[application_name]:
                downstreams[downstream_name] = self.addresses[downstream_name]
            self.start_processor(
                application_topic,
                infrastructure_topic,
                self.setup_tables,
                address,
                upstreams,
                downstreams,
            )

    def start_processor(
        self,
        application_topic,
        infrastructure_topic,
        setup_table,
        address,
        upstreams,
        downstreams,
    ):
        """
        Starts a gRPC process.
        """
        os.environ["DB_URI"] = (
            "mysql+pymysql://{}:{}@{}/eventsourcing{}?charset=utf8mb4&binary_prefix=true"
        ).format(
            os.getenv("MYSQL_USER", "eventsourcing"),
            os.getenv("MYSQL_PASSWORD", "eventsourcing"),
            os.getenv("MYSQL_HOST", "127.0.0.1"),
            resolve_topic(application_topic).create_name()
            if self.use_individual_databases
            else "",
        )

        process = Popen(
            [
                sys.executable,
                processor.__file__,
                application_topic,
                infrastructure_topic,
                json.dumps(setup_table),
                address,
                json.dumps(upstreams),
                json.dumps(downstreams),
                json.dumps(self.push_prompt_interval),
            ],
            stderr=subprocess.STDOUT,
            close_fds=True,
            env=os.environ.copy(),
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
        self, process_class: Type[TProcessApplication]
    ) -> TProcessApplication:
        client = ProcessorClient()
        client.connect(self.addresses[process_class.create_name()])
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
