import weakref
from _weakref import ReferenceType
from abc import ABC, abstractmethod
from collections import OrderedDict
from copy import deepcopy
from typing import Any, Dict, List, Optional, Type, TypeVar

from eventsourcing.application.popo import PopoApplication
from eventsourcing.application.process import ProcessApplication
from eventsourcing.application.simple import ApplicationWithConcreteInfrastructure
from eventsourcing.exceptions import EventSourcingError, ProgrammingError

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
        follows which other process in the system.

        For example, the pipeline expression (A | B | C) shows that B follows A,
        and C follows B.

        The pipeline expression (A | A) shows that A follows A.

        The pipeline expression (A | B | A) shows that B follows A, and A follows B.

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
                process_name = process_class.__name__.lower()
                if process_name not in self.process_classes:
                    self.process_classes[process_name] = process_class

        self.runner: Optional[ReferenceType] = None
        self.is_session_shared = True
        self.shared_session = None

        # Determine which process follows which.
        self.followers: OrderedDict[str, List[str]] = OrderedDict()
        # A following is a list of process classes followed by a process class.
        # Todo: Factor this out, it's confusing. (Only used in ActorModelRunner now).
        self.followings: OrderedDict[str, List[str]] = OrderedDict()
        for pipeline_expr in self.pipelines_exprs:
            previous_name = None
            for process_class in pipeline_expr:
                process_name = process_class.__name__.lower()
                try:
                    follows = self.followings[process_name]
                except KeyError:
                    follows = []
                    self.followings[process_name] = follows

                try:
                    self.followers[process_name]
                except KeyError:
                    self.followers[process_name] = []

                if previous_name and previous_name not in follows:
                    follows.append(previous_name)
                    followers = self.followers[previous_name]
                    followers.append(process_name)

                previous_name = process_name

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
        self.runner = weakref.ref(runner)
        return runner

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Supports usage of a system object as a context manager.
        """

        if self.runner:
            runner: Optional[AbstractSystemRunner] = self.runner()
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
        assert isinstance(self, AbstractSystemRunner)  # For PyCharm navigation.
        if self.system.runner is None or self.system.runner() is None:
            self.system.runner = weakref.ref(self)
        else:
            raise ProgrammingError(
                "System is already running: {}".format(self.system.runner)
            )

        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Supports usage of a system runner as a context manager.
        """
        self.close()
        self.system.runner = None

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

    def get(self, process_class: Type[TProcessApplication]) -> TProcessApplication:
        process_name = process_class.__name__.lower()
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
