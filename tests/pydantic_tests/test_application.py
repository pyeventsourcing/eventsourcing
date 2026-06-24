from unittest import TestCase

from eventsourcing.application import Application
from eventsourcing.persistence import InfrastructureFactory, NullTranscoder
from eventsourcing.pydantic.mapper import PydanticMapper
from eventsourcing.utils import get_topic


class TestApplicationWithPydanticMapper(TestCase):
    def test_does_not_register_transcodings(self) -> None:
        # This test exists simply to cover the branch in construct_transcoder()
        # where transcodings are not registered. Which isn't covered by
        # PydanticApplication, because it overrides construct_mapper().
        Application(
            env={
                InfrastructureFactory.MAPPER_TOPIC: get_topic(PydanticMapper),
                InfrastructureFactory.TRANSCODER_TOPIC: get_topic(NullTranscoder),
            }
        )


# TODO: Add more tests here to cover everything in `eventsourcing.pydantic` :-)
#   which are covered only by the aggregate examples at the moment.
