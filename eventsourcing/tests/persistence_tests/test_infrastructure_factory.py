from unittest.case import TestCase

from eventsourcing.persistence import InfrastructureFactory
from eventsourcing.utils import Environment, get_topic


class TestInfrastructureFactoryErrors(TestCase):
    def test_construct_raises_exception(self):
        with self.assertRaises(EnvironmentError):
            InfrastructureFactory.construct(
                Environment(
                    env={InfrastructureFactory.PERSISTENCE_MODULE: "invalid topic"}
                )
            )

        with self.assertRaises(AssertionError):
            InfrastructureFactory.construct(
                Environment(
                    env={InfrastructureFactory.PERSISTENCE_MODULE: get_topic(object)}
                )
            )
