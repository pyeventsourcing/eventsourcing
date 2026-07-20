from typing import TYPE_CHECKING
from unittest.case import TestCase

import eventsourcing.popo
from eventsourcing.dataclasses.legacy import LegacyJSONTranscoder
from eventsourcing.errors import InfrastructureFactoryError, ProgrammingError
from eventsourcing.persistence import (
    AggregateEventMapper,
    ApplicationRecorder,
    EventStore,
    InfrastructureFactory,
    Mapper,
    TrackingRecorder,
)
from eventsourcing.utils import Environment, get_topic

if TYPE_CHECKING:
    from eventsourcing.dataclasses.immutable import DataclassDecision


class TestInfrastructureFactory(TestCase):
    def test_constructs_popo_factory_by_default(self) -> None:
        factory: InfrastructureFactory[TrackingRecorder] = (
            InfrastructureFactory.construct()
        )
        self.assertIsInstance(factory, InfrastructureFactory)
        self.assertIsInstance(factory, eventsourcing.popo.POPOFactory)

    def test_construct_raises_exception_when_persistence_module_is_invalid(
        self,
    ) -> None:
        with self.assertRaises(InfrastructureFactoryError):
            InfrastructureFactory.construct(
                Environment(
                    env={InfrastructureFactory.PERSISTENCE_MODULE: "invalid topic"}
                )
            )

        with self.assertRaises(InfrastructureFactoryError):
            InfrastructureFactory.construct(
                Environment(
                    env={InfrastructureFactory.PERSISTENCE_MODULE: get_topic(object)}
                )
            )

    def test_construct_mapper(self) -> None:
        # No environment variables.
        factory: InfrastructureFactory[TrackingRecorder] = (
            InfrastructureFactory.construct()
        )
        with self.assertRaises(ProgrammingError) as cm:
            factory.mapper()
        self.assertIn("Please set TRANSCODER_TOPIC", str(cm.exception))

        env = {
            InfrastructureFactory.TRANSCODER_TOPIC: get_topic(LegacyJSONTranscoder),
        }

        factory = InfrastructureFactory.construct(env)
        mapper: Mapper[DataclassDecision] = factory.mapper()

        self.assertIsInstance(mapper, AggregateEventMapper)
        self.assertIsInstance(mapper.transcoder, LegacyJSONTranscoder)

        # MYAPP_MAPPER_TOPIC set to MyMapper.
        env = {
            "MYAPP_"
            + InfrastructureFactory.MAPPER_TOPIC: get_topic(AggregateEventMapper),
            "MYAPP_"
            + InfrastructureFactory.TRANSCODER_TOPIC: get_topic(LegacyJSONTranscoder),
        }
        factory = InfrastructureFactory.construct(env=Environment("MyApp", env))
        mapper = factory.mapper()
        self.assertIsInstance(mapper, AggregateEventMapper)
        self.assertIsInstance(mapper.transcoder, LegacyJSONTranscoder)

    def test_construct_event_store(self) -> None:
        factory: InfrastructureFactory[TrackingRecorder] = (
            InfrastructureFactory.construct(
                env={
                    "MAPPER_TOPIC": get_topic(AggregateEventMapper),
                    "TRANSCODER_TOPIC": get_topic(LegacyJSONTranscoder),
                }
            )
        )
        event_store: EventStore[DataclassDecision] = factory.event_store()
        self.assertIsInstance(event_store, EventStore)
        self.assertIsInstance(event_store.mapper, AggregateEventMapper)
        self.assertIsInstance(event_store.recorder, ApplicationRecorder)

        my_mapper: Mapper[DataclassDecision] = factory.mapper()
        event_store = factory.event_store(mapper=my_mapper)
        self.assertEqual(id(event_store.mapper), id(my_mapper))

        my_recorder = factory.aggregate_recorder()
        event_store = factory.event_store(recorder=my_recorder)
        self.assertEqual(id(event_store.recorder), id(my_recorder))
