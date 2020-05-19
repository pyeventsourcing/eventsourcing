import weakref
from abc import ABC, abstractmethod
from collections import OrderedDict
from copy import deepcopy
from typing import Any, Dict, List, Optional, Type, TypeVar

from _weakref import ReferenceType
from eventsourcing.application.popo import PopoApplication
from eventsourcing.application.process import ProcessApplication
from eventsourcing.application.simple import ApplicationWithConcreteInfrastructure
from eventsourcing.exceptions import ProgrammingError
from eventsourcing.infrastructure.base import DEFAULT_PIPELINE_ID

TProcessApplication = TypeVar("TProcessApplication", bound=ProcessApplication)
TSystemRunner = TypeVar("TSystemRunner", bound="AbstractSystemRunner")
TSystem = TypeVar("TSystem", bound="System")


class System(object):
    """
    A system object has a set of pipeline expressions, which involve
    process application classes. A system object can be run using
    a system runner.

    """

    def __init__(self, *pipeline_exprs: Any, **kwargs: Any):
        """
        Initialises a "process network" system object.

        Each pipeline expression of process classes shows directly which process
        following which other process in the system.

        For example, the pipeline expression (A | B | C) shows that B following A,
        and C following B.

        The pipeline expression (A | A) shows that A following A.

        The pipeline expression (A | B | A) shows that B following A, and A following B.

        The pipeline expressions ((A | B | A), (A | C | A)) are equivalent to (A | B
        | A | C | A).

        :param pipeline_exprs: Pipeline expressions involving process application
        classes.
        """
        self.pipelines_exprs = pipeline_exprs
        self.setup_tables = kwargs.get("setup_tables", False)
        self.infrastructure_class = kwargs.get("infrastructure_class", None)
        self.use_direct_query_if_available = kwargs.get(
            "use_direct_query_if_available", False
        )

        self.session = kwargs.get("session", None)
        self.shared_session = None

        self.process_classes: OrderedDict[str, Type[ProcessApplication]] = OrderedDict()
        for pipeline_expr in self.pipelines_exprs:
            for process_class in pipeline_expr:
                process_name = process_class.create_name()
                if process_name not in self.process_classes:
                    self.process_classes[process_name] = process_class

        self.runner: Optional[ReferenceType] = None
        self.is_session_shared = True
        self.shared_session = None

        # Construct pipeline graph.
        self.downstream_names: OrderedDict[str, List[str]] = OrderedDict()
        self.upstream_names: OrderedDict[str, List[str]] = OrderedDict()

        edges = []
        nodes = []
        for pipeline_expr in self.pipelines_exprs:
            previous_name = None
            for process_class in pipeline_expr:
                process_name = process_class.create_name()
                if process_name not in nodes:
                    nodes.append(process_name)
                if previous_name:
                    edges.append((previous_name, process_name))
                previous_name = process_name

        for process_name in nodes:
            self.downstream_names[process_name] = []
            self.upstream_names[process_name] = []

        for upstream_name, downstream_name in edges:
            self.downstream_names[upstream_name].append(downstream_name)
            self.upstream_names[downstream_name].append(upstream_name)

        self.nodes_of_pipeline_spec = nodes
        self.edges_of_pipeline_spec = edges

    def construct_app(
        self,
        process_class: Type[TProcessApplication],
        infrastructure_class: Optional[
            Type[ApplicationWithConcreteInfrastructure]
        ] = None,
        **kwargs: Any,
    ) -> TProcessApplication:
        """
        Constructs process application from given ``process_class``.
        """

        # If process class isn't already an infrastructure class, then
        # subclass the process class with concrete infrastructure.
        if not issubclass(process_class, ApplicationWithConcreteInfrastructure):

            # Default to PopoApplication infrastructure.
            if infrastructure_class is None:
                infrastructure_class = self.infrastructure_class or PopoApplication

            # Assert that we now have an application with concrete infrastructure.
            if not issubclass(
                infrastructure_class, ApplicationWithConcreteInfrastructure
            ):
                raise ProgrammingError(
                    "Given infrastructure_class {} is not subclass of {}"
                    "".format(
                        infrastructure_class, ApplicationWithConcreteInfrastructure
                    )
                )

            # Subclass the process application class with the infrastructure class.
            process_class = process_class.mixin(infrastructure_class)

        assert issubclass(process_class, ApplicationWithConcreteInfrastructure)

        # Set 'session' and 'setup_table' in kwargs.
        kwargs = dict(kwargs)
        if "session" not in kwargs and process_class.is_constructed_with_session:
            kwargs["session"] = self.session or self.shared_session
        if "setup_tables" not in kwargs and self.setup_tables:
            kwargs["setup_table"] = self.setup_tables

        # Construct the process application.
        app = process_class(**kwargs)

        # Catch the session, so it can be shared.
        if self.session is None and self.shared_session is None:
            if process_class.is_constructed_with_session and self.is_session_shared:
                if self.shared_session is None:
                    self.shared_session = app.session

        assert isinstance(app, ProcessApplication), app
        return app

    def __enter__(self) -> "AbstractSystemRunner":
        """
        Supports running a system object directly as a context manager.

        The system is run with the SingleThreadedRunner.
        """
        from eventsourcing.system.runner import SingleThreadedRunner

        if self.runner:
            raise ProgrammingError("System is already running: {}".format(self.runner))

        runner = SingleThreadedRunner(
            system=self,
            use_direct_query_if_available=self.use_direct_query_if_available,
        )
        runner.start()
        self.runner = runner
        return runner

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Supports usage of a system object as a context manager.
        """

        if self.runner:
            runner: Optional[AbstractSystemRunner] = self.runner
            if runner is not None:
                runner.close()
            self.runner = None

    def bind(
        self: TSystem, infrastructure_class: Type[ApplicationWithConcreteInfrastructure]
    ) -> TSystem:
        """
        Constructs a system object that has an infrastructure class
        from a system object constructed without infrastructure class.

        Raises ProgrammingError if already have an infrastructure class.

        :param infrastructure_class:
        :return: System object that has an infrastructure class.
        :rtype: System
        """
        # Check system doesn't already have an infrastructure class.

        if self.infrastructure_class:
            raise ProgrammingError("System already has an infrastructure class")

        # Clone the system object, and set the infrastructure class.
        system = type(self).__new__(type(self))
        system.__dict__.update(dict(deepcopy(self.__dict__)))
        system.__dict__.update(infrastructure_class=infrastructure_class)
        return system


class AbstractSystemRunner(ABC):
    def __init__(
        self,
        system: System,
        infrastructure_class: Optional[
            Type[ApplicationWithConcreteInfrastructure]
        ] = None,
        setup_tables: bool = False,
        use_direct_query_if_available: bool = False,
    ):
        self.system = system
        self.infrastructure_class = (
            infrastructure_class or self.system.infrastructure_class
        )
        self.setup_tables = setup_tables
        self.use_direct_query_if_available = (
            use_direct_query_if_available or system.use_direct_query_if_available
        )
        self.processes: Dict[str, Any] = {}

    def __enter__(self: TSystemRunner) -> TSystemRunner:
        """
        Supports usage of a system runner as a context manager.
        """
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Supports usage of a system runner as a context manager.
        """
        self.close()

    @abstractmethod
    def start(self) -> None:
        """
        Starts running the system.

        Abstract method which must be implemented on concrete descendants.
        """

    def close(self) -> None:
        """
        Closes a running system.
        """
        self.system.shared_session = None
        if self.processes:
            process: ProcessApplication
            for process in self.processes.values():
                process.close()
            self.processes.clear()

    def get_class(self, process_name: str) -> Type[ProcessApplication]:
        return self.system.process_classes[process_name]

    def get(
        self, process_class: Type[TProcessApplication], pipeline_id=DEFAULT_PIPELINE_ID
    ) -> TProcessApplication:
        process_name = process_class.create_name()
        try:
            process = self.processes[process_name]
        except KeyError:
            process = self._construct_app_by_class(process_class)
        return process

    def _construct_app_by_class(
        self, process_class: Type[TProcessApplication]
    ) -> TProcessApplication:
        process = self.system.construct_app(
            process_class=process_class,
            infrastructure_class=self.infrastructure_class,
            setup_table=self.setup_tables or self.system.setup_tables,
            use_direct_query_if_available=self.use_direct_query_if_available,
        )
        self.processes[process.name] = process
        return process
