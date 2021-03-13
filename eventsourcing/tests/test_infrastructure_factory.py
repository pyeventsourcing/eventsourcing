import os
from unittest.case import TestCase

from eventsourcing.persistence import InfrastructureFactory
from eventsourcing.utils import get_topic


class TestInfrastructureFactoryErrors(TestCase):
    def tearDown(self) -> None:
        del os.environ[InfrastructureFactory.TOPIC]

    def test_construct_raises_exception(self):
        os.environ[InfrastructureFactory.TOPIC] = "invalid topic"
        with self.assertRaises(EnvironmentError):
            InfrastructureFactory.construct("")

        os.environ[InfrastructureFactory.TOPIC] = get_topic(object)
        with self.assertRaises(AssertionError):
            InfrastructureFactory.construct("")
