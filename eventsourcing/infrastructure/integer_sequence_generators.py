from abc import abstractmethod
from uuid import uuid4

from redis import StrictRedis


class AbstractIntegerSequenceGenerator(object):
    @abstractmethod
    def __iter__(self):
        """
        Returns an iterable that yields integers.
        """


class SimpleIntegerSequenceGenerator(AbstractIntegerSequenceGenerator):
    def __iter__(self):
        i = 0
        while True:
            yield i
            i += 1


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
