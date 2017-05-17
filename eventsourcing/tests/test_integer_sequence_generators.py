from eventsourcing.infrastructure.integer_sequence_generators import RedisIncr, \
    SimpleIntegerSequenceGenerator
from eventsourcing.tests.base import AbstractTestCase


class IntegerSequenceGeneratorTestCase(AbstractTestCase):
    generator_class = None

    def test(self):
        g = self.generator_class()
        limit = 500
        for i, j in enumerate(g):
            self.assertEqual(i, j)
            if i == limit:
                break
        self.assertEqual(i, limit)


class TestSimpleIntegerSequenceGenerator(IntegerSequenceGeneratorTestCase):
    generator_class = SimpleIntegerSequenceGenerator


class TestRedisIncr(IntegerSequenceGeneratorTestCase):
    generator_class = RedisIncr
