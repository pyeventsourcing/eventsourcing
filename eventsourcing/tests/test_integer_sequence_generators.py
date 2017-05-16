from redis.client import StrictRedis

from eventsourcing.infrastructure.integer_sequence_generators import RedisIntegerSequenceGenerator, \
    SimpleIntegerSequenceGenerator
from eventsourcing.tests.base import AbstractTestCase


class IntegerSequenceGeneratorTestCase(AbstractTestCase):
    generator_class = None
    def test(self):
        r= StrictRedis()

        g = self.generator_class()
        r.set(g.name, 9223372036854775807)
        limit = 5000
        for i1, i2 in enumerate(g):
            self.assertEqual(i1, i2)
            if i1 == limit:
                break

        self.assertEqual(i1, limit)


class TestRedisIntegerSequenceGenerator(IntegerSequenceGeneratorTestCase):
    generator_class = RedisIntegerSequenceGenerator


class TestSimpleIntegerSequenceGenerator(IntegerSequenceGeneratorTestCase):
    generator_class = SimpleIntegerSequenceGenerator
