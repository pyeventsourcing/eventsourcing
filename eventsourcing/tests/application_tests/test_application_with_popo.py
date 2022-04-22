from eventsourcing.tests.application import (
    TIMEIT_FACTOR,
    ApplicationTestCase,
    ExampleApplicationTestCase,
)


class TestApplicationWithPOPO(ApplicationTestCase):
    def test_application_fastforward_skipping_during_contention(self):
        self.skipTest("POPO is too fast for this test to work")

    def test_application_fastforward_blocking_during_contention(self):
        self.skipTest("POPO is too fast for this test to make sense")


class TestExampleApplicationWithPOPO(ExampleApplicationTestCase):
    timeit_number = 100 * TIMEIT_FACTOR
    expected_factory_topic = "eventsourcing.popo:Factory"


del ApplicationTestCase
del ExampleApplicationTestCase
