from __future__ import annotations

import contextlib
import os
import threading
import weakref
from abc import ABC, abstractmethod
from traceback import format_exc
from typing import TYPE_CHECKING, Any, override
from warnings import warn

from eventsourcing.application import (
    AbstractApplicationSubscription,
    AggregatesApplication,
    ProcessingEvent,
    SupportsApplicationSubscriptions,
)
from eventsourcing.domain import StreamEvent
from eventsourcing.errors import WaitInterruptedError
from eventsourcing.metadata import put_metadata_in_context
from eventsourcing.persistence import (
    InfrastructureFactory,
    ProcessRecorder,
    Tracking,
    TrackingRecorder,
)
from eventsourcing.types import ClosingContextManager
from eventsourcing.utils import Environment, EnvType

if TYPE_CHECKING:
    from collections.abc import Sequence


class AbstractPolicy[TEvent](ABC):
    topics: Sequence[str] = ()
    """
    Event topics, used to filter events in database when subscribing to an application.
    """

    @abstractmethod
    def process_event(self, envelope: TEvent, tracking: Tracking) -> None:
        """Process a domain event and track it."""


class ReadModelPolicy[TEvent, TReadModel](AbstractPolicy[TEvent], ABC):
    name: str = ""
    """
    Name of policy, used to pick prefixed environment
    variables and define database table names.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "name" not in cls.__dict__:
            cls.name = cls.__name__

    def __init__(
        self,
        read_model: TReadModel,
    ):
        """Initialises the read_model property."""
        self._read_model = read_model

    @property
    def read_model(self) -> TReadModel:
        """Materialised view of an event-sourced application."""
        return self._read_model


class AggregatesApplicationPolicy[TUpstreamDecision, TDownstreamDecision](
    AggregatesApplication[ProcessRecorder, TDownstreamDecision],
    AbstractPolicy[StreamEvent[TUpstreamDecision]],
):
    """Extends the :py:class:`~eventsourcing.application.AggregatesApplication` class
    by using a process recorder as its application recorder, and by
    processing domain events through a :py:func:`policy` method.
    """

    def __init__(self, *, env: EnvType | None = None, context_name: str | None = None):
        super().__init__(env=env, context_name=context_name)
        self.processing_lock = threading.Lock()

    @override
    def construct_recorder(self) -> ProcessRecorder:
        """Constructs and returns a :class:`~eventsourcing.persistence.ProcessRecorder`
        for the application to use as its application recorder.
        """
        return self.factory.process_recorder()

    @override
    def process_event(
        self, envelope: StreamEvent[TUpstreamDecision], tracking: Tracking
    ) -> None:
        """
        Calls :func:`~eventsourcing.projection.AggregatesApplicationPolicy.policy`
        method with the given domain event and a new
        :class:`~eventsourcing.application.ProcessingEvent`
        constructed with the given tracking object.

        The policy method should collect any new aggregate events on the
        process event object.

        After the policy method returns, the processing event object
        will be recorded by calling
        :py:func:`~eventsourcing.application.AggregatesApplication._record`,
        which then returns list of :py:class:`~eventsourcing.persistence.Recording`.

        After calling :func:`~eventsourcing.application.Application._take_snapshots`,
        the notification_id is passed in a call to
        :py:func:`~eventsourcing.application.Application._notify`.
        """
        processing_event = ProcessingEvent[TDownstreamDecision](tracking=tracking)
        metadata = {}
        with contextlib.suppress(KeyError):
            metadata["correlation_id"] = envelope.metadata["correlation_id"]
            metadata["causation_id"] = str(envelope.event_id)
        with put_metadata_in_context(metadata):
            self.policy(envelope, processing_event)
        notification_id = self._record(processing_event)
        self._take_snapshots(processing_event)
        self._notify(notification_id)

    @abstractmethod
    def policy(
        self,
        envelope: StreamEvent[TUpstreamDecision],
        processing_event: ProcessingEvent[TDownstreamDecision],
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


class EventConsumer[TApplication: SupportsApplicationSubscriptions[Any, Any]](
    ClosingContextManager
):
    def __init__(
        self,
        *,
        upstream: TApplication,
        policy: AbstractPolicy[Any],
        tracking_recorder: TrackingRecorder,
        topics: Sequence[str],
    ) -> None:
        self.upstream = upstream
        self._is_interrupted = threading.Event()
        self._has_called_stop = False
        self._tracking_recorder = tracking_recorder

        # Subscribe to the upstream application.
        try:
            self._subscription = upstream.application_subscription(
                gt=tracking_recorder.max_tracking_id(upstream.context_name),
                topics=topics,
            )

            # Start a thread to stop the subscription when the runner is interrupted.
            self.thread_error: BaseException | None = None
            self._stop_thread = threading.Thread(
                target=self._stop_subscription_when_stopping,
                kwargs={
                    "subscription": self._subscription,
                    "is_stopping": self._is_interrupted,
                },
            )
            self._stop_thread.start()

            # Start a thread to iterate over the subscription.
            self._consumer_thread = threading.Thread(
                target=self._consumer_loop,
                kwargs={
                    "subscription": self._subscription,
                    "policy": policy,
                    "is_stopping": self._is_interrupted,
                    "consumer": weakref.ref(self),
                },
            )
            self._consumer_thread.start()
        except BaseException:
            self.stop()
            if hasattr(self, "_stop_thread") and self._stop_thread.is_alive():
                self._stop_thread.join()
            elif hasattr(self, "_subscription"):
                self._subscription.stop()
            self.upstream.close()
            raise

    @property
    def is_interrupted(self) -> threading.Event:
        return self._is_interrupted

    @staticmethod
    def _construct_env(name: str, env: EnvType | None = None) -> Environment:
        """
        Constructs environment from which the policy and application will be configured.
        """
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
    def _consumer_loop(
        subscription: AbstractApplicationSubscription[Any],
        policy: AbstractPolicy[Any],
        is_stopping: threading.Event,
        consumer: weakref.ReferenceType[Any],
    ) -> None:
        """Iterates over the subscription and calls process_event()."""
        try:
            for envelope, tracking in subscription:
                policy.process_event(envelope, tracking)
        except BaseException as e:
            _consumer = consumer()  # get reference from weakref
            if _consumer is not None:
                _consumer.thread_error = e
            else:
                msg = "Event consumer was deleted before error could be assigned:\n"
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
        if self._is_interrupted.wait(timeout=timeout) and self.thread_error is not None:
            error = self.thread_error
            self.thread_error = None
            raise error from None

    def wait(self, notification_id: int | None, timeout: float = 1.0) -> None:
        """Blocks until timeout, or until the materialised view has recorded a tracking
        object that is greater than or equal to the given notification ID.
        """
        try:
            self._tracking_recorder.wait(
                context_name=self.upstream.context_name,
                notification_id=notification_id,
                timeout=timeout,
                interrupt=self._is_interrupted,
            )
        except WaitInterruptedError as e:
            if self.thread_error:
                error = self.thread_error
                self.thread_error = None
                raise error from None
            if self._has_called_stop:
                return
            raise e from None

    @override
    def close(self) -> None:
        try:
            self.stop()
            if hasattr(self, "_stop_thread"):
                self._stop_thread.join()
            if hasattr(self, "_consumer_thread"):
                self._consumer_thread.join()
        finally:
            try:
                self.upstream.close()
            except Exception:
                if getattr(self, "thread_error", None) is None:
                    raise
            thread_error = getattr(self, "thread_error", None)
            if thread_error is not None:
                self.thread_error = None
                raise thread_error


class ReadModelRunner[
    TUpstream: SupportsApplicationSubscriptions[Any, Any],
    TPolicy: ReadModelPolicy[Any, Any],
    TReadModel: TrackingRecorder,
](
    EventConsumer[TUpstream],
):
    def __init__(
        self,
        *,
        upstream_class: type[TUpstream],
        policy_class: type[TPolicy],
        read_model_class: type[TReadModel],
        env: EnvType | None = None,
    ):
        """Constructs application from given application class with given environment.
        Also constructs a materialised view from given class using an infrastructure
        factory constructed with an environment named after the policy. Also
        constructs a policy with the constructed materialised view object.
        Starts a subscription to application and, in a separate event-processing
        thread, calls policy's process_event() method for each event and tracking
        object pair received from the subscription.
        """
        # Construct the materialised view using an infrastructure factory.
        self._factory = InfrastructureFactory[TReadModel].construct(
            env=self._construct_env(name=policy_class.name, env=env)
        )
        try:
            # Construct the policy.
            self.read_model = self._factory.tracking_recorder(read_model_class)
            self.policy = policy_class(read_model=self.read_model)

            super().__init__(
                upstream=upstream_class(env=env),
                policy=self.policy,
                tracking_recorder=self.read_model,
                topics=self.policy.topics,
            )
        except BaseException:
            self._factory.close()
            raise

    @override
    def close(self) -> None:
        try:
            super().close()
        finally:
            self._factory.close()


class AggregatesApplicationRunner[
    TUpstream: SupportsApplicationSubscriptions[Any, Any],
    TDownstream: AggregatesApplicationPolicy[Any, Any],
](
    EventConsumer[TUpstream],
):
    def __init__(
        self,
        *,
        upstream_class: type[TUpstream],
        downstream_class: type[TDownstream],
        env: EnvType | None = None,
    ):
        self.downstream = downstream_class(
            env=self._construct_env(name=downstream_class.context_name, env=env)
        )
        try:
            super().__init__(
                upstream=upstream_class(env=env),
                policy=self.downstream,
                tracking_recorder=self.downstream.recorder,
                topics=self.downstream.topics,
            )
        except BaseException:
            self.downstream.close()
            raise

    @override
    def close(self) -> None:
        try:
            super().close()
        finally:
            self.downstream.close()
