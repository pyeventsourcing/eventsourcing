# Todo Make this runner work :-)
from eventsourcing.system.definition import AbstractSystemRunner


class KubernetesRunner(AbstractSystemRunner):
    """
    Builds a Docker image with the whole system,
    that runs a grpc.processor.ProcessorServer when it
    starts, for a process application, according
    to environment variable.

    Generates the YAML Deployment files, one
    Deployment per process application class
    using the above Docker image, with environment
    variables to configure (1) which process application
    class is run by the ProcessorServer, and (2) which
    other processes are upstream and downstream.

    Todo: Improve the ProcessorClient so they reconnect
    when a deployment ("pod") goes down and comes back
    up again.
    """
