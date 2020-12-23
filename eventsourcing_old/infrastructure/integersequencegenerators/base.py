from abc import abstractmethod
from threading import Lock


class AbstractIntegerSequenceGenerator(object):
    """
    Abstract base class for generating a sequence of integers.
    """

    def __iter__(self) -> "AbstractIntegerSequenceGenerator":
        return self

    @abstractmethod
    def __next__(self) -> int:
        """
        Returns the next item in the container.
        """


class SimpleIntegerSequenceGenerator(AbstractIntegerSequenceGenerator):
    """
    Generates a sequence of integers, by simply incrementing a Python int.
    """

    def __init__(self, i: int = 0):
        self.i = i
        self.lock = Lock()

    def __next__(self) -> int:
        """
        Returns the next item in the container.
        """
        self.lock.acquire()
        i = self.i
        self.i += 1
        self.lock.release()
        return i
