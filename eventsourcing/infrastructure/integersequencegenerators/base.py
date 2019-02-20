from abc import abstractmethod
from threading import Lock


class AbstractIntegerSequenceGenerator(object):

    def __iter__(self):
        return self

    @abstractmethod
    def __next__(self):
        """
        Returns the next item in the container.
        """


class SimpleIntegerSequenceGenerator(AbstractIntegerSequenceGenerator):

    def __init__(self, i=0):
        self.i = i
        self.lock = Lock()

    def __next__(self):
        self.lock.acquire()
        i = self.i
        self.i += 1
        self.lock.release()
        return i
