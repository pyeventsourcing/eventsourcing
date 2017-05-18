from uuid import uuid4

from redis import StrictRedis

from eventsourcing.infrastructure.integersequencegenerators.base import AbstractIntegerSequenceGenerator


class RedisIncr(AbstractIntegerSequenceGenerator):
    """
    Generates a sequence of integers, using Redis' INCR command.
    
    Maximum number is 2**63, or 9223372036854775807, the maximum
    value of a 64 bit signed integer.
    """
    def __init__(self, redis=None, key=None):
        self.redis = redis
        self.key = key or 'integer-sequence-generator-{}'.format(uuid4())

    def __iter__(self):
        r = self.redis or StrictRedis()
        while True:
            yield r.incr(self.key) - 1
