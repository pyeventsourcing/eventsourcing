from uuid import uuid4

import os
from redis import StrictRedis

from eventsourcing.infrastructure.integersequencegenerators.base import AbstractIntegerSequenceGenerator


class RedisIncr(AbstractIntegerSequenceGenerator):
    """
    Generates a sequence of integers, using Redis' INCR command.

    Maximum number is 2**63, or 9223372036854775807, the maximum
    value of a 64 bit signed integer.
    """
    def __init__(self, redis=None, key=None):
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis = redis or StrictRedis(host=redis_host)
        self.key = key or 'integer-sequence-generator-{}'.format(uuid4())

    def __next__(self):
        return self.redis.incr(self.key) - 1
