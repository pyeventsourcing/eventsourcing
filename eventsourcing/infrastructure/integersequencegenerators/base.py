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

    def next(self):
        """
        Python 2.7 version of the iterator protocol.
        """
        return self.__next__()


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
