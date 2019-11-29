from abc import abstractmethod
from threading import Lock


class AbstractIntegerSequenceGenerator(object):
    def __iter__(self) -> "AbstractIntegerSequenceGenerator":
        return self

    @abstractmethod
    def __next__(self) -> int:
        """
        Returns the next item in the container.
        """


class SimpleIntegerSequenceGenerator(AbstractIntegerSequenceGenerator):
    def __init__(self, i: int = 0):
        self.i = i
        self.lock = Lock()

    def __next__(self) -> int:
        self.lock.acquire()
        i = self.i
        self.i += 1
        self.lock.release()
        return i
