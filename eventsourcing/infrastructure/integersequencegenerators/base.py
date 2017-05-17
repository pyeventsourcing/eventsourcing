from abc import abstractmethod


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
