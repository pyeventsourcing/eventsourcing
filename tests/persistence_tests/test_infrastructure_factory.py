from unittest.case import TestCase

import eventsourcing.popo
from eventsourcing.persistence import (
    ApplicationRecorder,
    DataclassMapper,
    EventStore,
    InfrastructureFactory,
    InfrastructureFactoryError,
    JSONTranscoder,
    Mapper,
)
from eventsourcing.utils import Environment, get_topic


class TestInfrastructureFactory(TestCase):
    def test_constructs_popo_factory_by_default(self) -> None:
        factory = InfrastructureFactory.construct()
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

    def test_construct_transcoder(self) -> None:
        # No environment variables.
        factory = InfrastructureFactory.construct()
        transcoder = factory.transcoder()
        self.assertIsInstance(transcoder, JSONTranscoder)

        # TRANSCODER_TOPIC set to JSONTranscoder.
        transcoder_topic = get_topic(JSONTranscoder)
        env = Environment(
            env={InfrastructureFactory.TRANSCODER_TOPIC: transcoder_topic}
        )
        factory = InfrastructureFactory.construct(env)
        transcoder = factory.transcoder()
        self.assertIsInstance(transcoder, JSONTranscoder)

        class MyTranscoder(JSONTranscoder):
            pass

        # TRANSCODER_TOPIC set to MyTranscoder.
        transcoder_topic = get_topic(MyTranscoder)
        env = Environment(
            env={InfrastructureFactory.TRANSCODER_TOPIC: transcoder_topic}
        )
        factory = InfrastructureFactory.construct(env)
        transcoder = factory.transcoder()
        self.assertIsInstance(transcoder, MyTranscoder)

        # MYAPP_TRANSCODER_TOPIC set to MyTranscoder.
        env = Environment(
            name="MyApp",
            env={"MYAPP_" + InfrastructureFactory.TRANSCODER_TOPIC: transcoder_topic},
        )
        factory = InfrastructureFactory.construct(env)
        transcoder = factory.transcoder()
        self.assertIsInstance(transcoder, MyTranscoder)

    def test_construct_mapper(self) -> None:
        # No environment variables.
        factory: InfrastructureFactory = InfrastructureFactory.construct()
        mapper: Mapper = factory.mapper()
        self.assertIsInstance(mapper, DataclassMapper)
        self.assertIsInstance(mapper.transcoder, JSONTranscoder)

        # MAPPER_TOPIC set to Mapper.
        env = Environment(
            env={InfrastructureFactory.MAPPER_TOPIC: get_topic(DataclassMapper)}
        )
        factory = InfrastructureFactory.construct(env)
        mapper = factory.mapper()
        self.assertIsInstance(mapper, DataclassMapper)

        class MyMapper(DataclassMapper):
            pass

        # MAPPER_TOPIC set to MyMapper.
        pydantic_topic = get_topic(MyMapper)
        env = Environment(
            env={
                InfrastructureFactory.MAPPER_TOPIC: pydantic_topic,
            }
        )
        factory = InfrastructureFactory.construct(env)
        mapper = factory.mapper()
        self.assertIsInstance(mapper, MyMapper)

        # MYAPP_MAPPER_TOPIC set to MyMapper.
        env = Environment(
            name="MyApp",
            env={
                "MYAPP_" + InfrastructureFactory.MAPPER_TOPIC: pydantic_topic,
            },
        )

        factory = InfrastructureFactory.construct(env=env)
        mapper = factory.mapper()
        self.assertIsInstance(mapper, MyMapper)

    def test_construct_event_store(self) -> None:
        factory: InfrastructureFactory = InfrastructureFactory.construct()
        event_store: EventStore = factory.event_store()
        self.assertIsInstance(event_store, EventStore)
        self.assertIsInstance(event_store.mapper, DataclassMapper)
        self.assertIsInstance(event_store.recorder, ApplicationRecorder)

        my_mapper: Mapper = factory.mapper()
        event_store = factory.event_store(mapper=my_mapper)
        self.assertEqual(id(event_store.mapper), id(my_mapper))

        my_recorder = factory.aggregate_recorder()
        event_store = factory.event_store(recorder=my_recorder)
        self.assertEqual(id(event_store.recorder), id(my_recorder))
