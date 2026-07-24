from __future__ import annotations

import contextlib
import os
import threading
import weakref
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from traceback import format_exc
from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar
from warnings import warn

from eventsourcing.application import (
    AbstractApplication,
    AbstractApplicationSubscription,
    AggregatesApplication,
    ProcessingEvent,
)
from eventsourcing.dcb.application import DcbApplication
from eventsourcing.domain import (
    TDecision,
    TEnvelope,
    put_metadata_in_context,
)
from eventsourcing.errors import WaitInterruptedError
from eventsourcing.persistence import (
    InfrastructureFactory,
    ProcessRecorder,
    Tracking,
    TrackingRecorder,
    TTrackingRecorder,
)
from eventsourcing.utils import Environment, EnvType

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import TracebackType


TApplication = TypeVar("TApplication", bound=AbstractApplication[Any, Any])
TAggregatesApplication = TypeVar(
    "TAggregatesApplication", bound=AggregatesApplication[Any]
)
TDcbApplication = TypeVar("TDcbApplication", bound=DcbApplication[Any])


class AbstractProjection(AbstractContextManager[Any], Generic[TEnvelope]):
    topics: Sequence[str] = ()
    """
    Event topics, used to filter events in database when subscribing to an application.
    """

    @abstractmethod
    def process_event(self, envelope: TEnvelope, tracking: Tracking) -> None:
        """Process a domain event and track it."""

    def __enter__(self) -> Self:
        # Self is perfectly valid here because it is inside the class block
        return super().__enter__()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
        /,
    ) -> bool | None:
        # Self is perfectly valid here because it is inside the class block
        return super().__exit__(exc_type, exc_value, traceback)


class Projection(
    AbstractProjection[TEnvelope], ABC, Generic[TTrackingRecorder, TEnvelope]
):
    name: str = ""
    """
    Name of projection, used to pick prefixed environment
    variables and define database table names.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        if "name" not in cls.__dict__:
            cls.name = cls.__name__

    def __init__(
        self,
        view: TTrackingRecorder,
    ):
        """Initialises the view property with the given view argument."""
        self._view = view

    @property
    def view(self) -> TTrackingRecorder:
        """Materialised view of an event-sourced application."""
        return self._view


class EventSourcedProjection(
    AggregatesApplication[TDecision],
    AbstractProjection[TEnvelope],
    Generic[TDecision, TTrackingRecorder, TEnvelope],
):
    """Extends the :py:class:`~eventsourcing.application.AggregatesApplication` class
    by using a process recorder as its application recorder, and by
    processing domain events through a :py:func:`policy` method.
    """

    recorder: ProcessRecorder

    def __init__(self, *, env: EnvType | None = None, context_name: str | None = None):
        super().__init__(env=env, context_name=context_name)
        self.processing_lock = threading.Lock()

    def construct_recorder(self) -> ProcessRecorder:
        """Constructs and returns a :class:`~eventsourcing.persistence.ProcessRecorder`
        for the application to use as its application recorder.
        """
        return self.factory.process_recorder()

    def process_event(self, envelope: TEnvelope, tracking: Tracking) -> None:
        """Calls :func:`~eventsourcing.system.Follower.policy` method with the given
        domain event and a new :class:`~eventsourcing.application.ProcessingEvent`
        constructed with the given tracking object.

        The policy method should collect any new aggregate events on the process
        event object.

        After the policy method returns, the processing event object will be recorded
        by calling :py:func:`~eventsourcing.application.Application._record`,
        which then returns list of :py:class:`~eventsourcing.persistence.Recording`.

        After calling :func:`~eventsourcing.application.Application._take_snapshots`,
        the recordings are passed in a call to
        :py:func:`~eventsourcing.application.Application._notify`.
        """
        processing_event = ProcessingEvent[TDecision](tracking=tracking)
        metadata = {}
        with contextlib.suppress(KeyError):
            metadata["correlation_id"] = envelope.metadata["correlation_id"]
            metadata["causation_id"] = str(envelope.uuid)
        with put_metadata_in_context(metadata):
            self.policy(envelope, processing_event)
        recordings = self._record(processing_event)
        self._take_snapshots(processing_event)
        self._notify(recordings)

    def policy(
        self,
        envelope: TEnvelope,
        processing_event: ProcessingEvent[TDecision],
    ) -> None:
        """Abstract domain event processing policy method. Must be
        implemented by event processing applications. When
        processing the given domain event, event processing
        applications must use the :func:`~ProcessingEvent.collect_events`
        method of the given :py:class:`~ProcessingEvent` object (not
        the application's :func:`~eventsourcing.application.Application.save`
        method) so that the new domain events will be recorded atomically
        and uniquely with tracking information about the position of the processed
        event in its application sequence.
        """


TProjection = TypeVar("TProjection", bound=Projection[Any, Any])
TEventSourcedProjection = TypeVar(
    "TEventSourcedProjection", bound=EventSourcedProjection[Any, Any, Any]
)


class BaseProjectionRunner(Generic[TApplication]):
    def __init__(
        self,
        *,
        projection: AbstractProjection[Any],
        app: TApplication,
        tracking_recorder: TrackingRecorder,
        topics: Sequence[str],
    ) -> None:
        self.app = app
        self._is_interrupted = threading.Event()
        self._has_called_stop = False
        self._tracking_recorder = tracking_recorder

        # Subscribe to the application.
        self._subscription = app.application_subscription(
            gt=tracking_recorder.max_tracking_id(app.context_name),
            topics=topics,
        )

        # Start a thread to stop the subscription when the runner is interrupted.
        self._thread_error: BaseException | None = None
        self._stop_thread = threading.Thread(
            target=self._stop_subscription_when_stopping,
            kwargs={
                "subscription": self._subscription,
                "is_stopping": self._is_interrupted,
            },
        )
        self._stop_thread.start()

        # Start a thread to iterate over the subscription.
        self._processing_thread = threading.Thread(
            target=self._process_events_loop,
            kwargs={
                "subscription": self._subscription,
                "projection": projection,
                "is_stopping": self._is_interrupted,
                "runner": weakref.ref(self),
            },
        )
        self._processing_thread.start()

    @property
    def is_interrupted(self) -> threading.Event:
        return self._is_interrupted

    @staticmethod
    def _construct_env(name: str, env: EnvType | None = None) -> Environment:
        """Constructs environment from which projection will be configured."""
        _env: dict[str, str] = {}
        _env.update(os.environ)
        if env is not None:
            _env.update(env)
        return Environment(name, _env)

    def stop(self) -> None:
        """Sets the "interrupted" event."""
        self._has_called_stop = True
        self._is_interrupted.set()

    @staticmethod
    def _stop_subscription_when_stopping(
        subscription: AbstractApplicationSubscription[Any],
        is_stopping: threading.Event,
    ) -> None:
        """Stops the application subscription, which
        will stop the event-processing thread.
        """
        try:
            is_stopping.wait()
        finally:
            is_stopping.set()
            subscription.stop()

    @staticmethod
    def _process_events_loop(
        subscription: AbstractApplicationSubscription[Any],
        projection: AbstractProjection[Any],
        is_stopping: threading.Event,
        runner: weakref.ReferenceType[Any],
    ) -> None:
        """Iterates over the subscription and calls process_event()."""
        try:
            for envelope, tracking in subscription:
                projection.process_event(envelope, tracking)
        except BaseException as e:
            _runner = runner()  # get reference from weakref
            if _runner is not None:
                _runner._thread_error = e  # noqa: SLF001
            else:
                msg = "ProjectionRunner was deleted before error could be assigned:\n"
                msg += format_exc()
                warn(
                    msg,
                    RuntimeWarning,
                    stacklevel=2,
                )
        finally:
            is_stopping.set()

    def run_forever(self, timeout: float | None = None) -> None:
        """Blocks until timeout, or until the runner is stopped or errors. Re-raises
        any error otherwise exits normally
        """
        if (
            self._is_interrupted.wait(timeout=timeout)
            and self._thread_error is not None
        ):
            error = self._thread_error
            self._thread_error = None
            raise error from None

    def wait(self, notification_id: int | None, timeout: float = 1.0) -> None:
        """Blocks until timeout, or until the materialised view has recorded a tracking
        object that is greater than or equal to the given notification ID.
        """
        try:
            self._tracking_recorder.wait(
                context_name=self.app.context_name,
                notification_id=notification_id,
                timeout=timeout,
                interrupt=self._is_interrupted,
            )
        except WaitInterruptedError as e:
            if self._thread_error:
                error = self._thread_error
                self._thread_error = None
                raise error from None
            if self._has_called_stop:
                return
            raise e from None

    def __enter__(self) -> Self:
        self._subscription.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Calls stop() and waits for the event-processing thread to exit."""
        self.stop()
        self._stop_thread.join()
        self._subscription.__exit__(exc_type, exc_val, exc_tb)
        self._processing_thread.join()
        # TODO: Improve typing of application classes and type annotation for self.app
        self.app.close()  # pyright: ignore [reportAttributeAccessIssue]
        if self._thread_error:
            error = self._thread_error
            self._thread_error = None
            raise error

    def __del__(self) -> None:
        """Calls stop()."""
        with contextlib.suppress(AttributeError):
            self.stop()


class ProjectionRunner(
    BaseProjectionRunner[TApplication],
    Generic[TApplication, TProjection, TTrackingRecorder],
):
    def __init__(
        self,
        *,
        application_class: type[TApplication],
        projection_class: type[TProjection],
        view_class: type[TTrackingRecorder],
        env: EnvType | None = None,
    ):
        """Constructs application from given application class with given environment.
        Also constructs a materialised view from given class using an infrastructure
        factory constructed with an environment named after the projection. Also
        constructs a projection with the constructed materialised view object.
        Starts a subscription to application and, in a separate event-processing
        thread, calls projection's process_event() method for each event and tracking
        object pair received from the subscription.
        """
        # Construct the materialised view using an infrastructure factory.
        factory: InfrastructureFactory[TTrackingRecorder] = (
            InfrastructureFactory.construct(
                env=self._construct_env(name=projection_class.name, env=env)
            )
        )
        self.view = factory.tracking_recorder(view_class)

        # Construct the projection using the materialised view.
        self.projection = projection_class(view=self.view)

        super().__init__(
            projection=self.projection,
            app=application_class(env=env),
            tracking_recorder=self.projection.view,
            topics=self.projection.topics,
        )


class EventSourcedProjectionRunner(
    BaseProjectionRunner[TApplication],
    Generic[TApplication, TEventSourcedProjection],
):
    def __init__(
        self,
        *,
        application_class: type[TApplication],
        projection_class: type[TEventSourcedProjection],
        env: EnvType | None = None,
    ):
        self.projection = projection_class(
            env=self._construct_env(name=projection_class.context_name, env=env)
        )

        super().__init__(
            projection=self.projection,
            app=application_class(env=env),
            tracking_recorder=self.projection.recorder,
            topics=self.projection.topics,
        )

    def __enter__(self) -> Self:
        cm = super().__enter__()
        self.projection.__enter__()
        return cm

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.projection.__exit__(exc_type, exc_val, exc_tb)
        return super().__exit__(exc_type, exc_val, exc_tb)
