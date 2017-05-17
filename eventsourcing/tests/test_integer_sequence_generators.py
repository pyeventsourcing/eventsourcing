from eventsourcing.infrastructure.integersequencegenerators.base import SimpleIntegerSequenceGenerator
from eventsourcing.infrastructure.integersequencegenerators.redisincr import RedisIncr
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
        else:
            self.fail('There were no items in the sequence')
        self.assertEqual(i, limit)


class TestSimpleIntegerSequenceGenerator(IntegerSequenceGeneratorTestCase):
    generator_class = SimpleIntegerSequenceGenerator


class TestRedisIncr(IntegerSequenceGeneratorTestCase):
    generator_class = RedisIncr
