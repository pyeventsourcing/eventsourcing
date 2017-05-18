from abc import abstractmethod
from threading import Lock


class AbstractIntegerSequenceGenerator(object):
    @abstractmethod
    def __next__(self):
        """
        Returns an iterable that yields integers.
        """


class SimpleIntegerSequenceGenerator(AbstractIntegerSequenceGenerator):

    def __init__(self, i=0):
        self.i = i
        self.lock = Lock()

    def __next__(self):
        while True:
            self.lock.acquire()
            i = self.i
            self.i += 1
            self.lock.release()
            return i
