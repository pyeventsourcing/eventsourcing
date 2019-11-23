from abc import ABCMeta
from typing import Iterator, Union

# Need to deal with the fact that Python3.6 had GenericMeta.
try:
    from typing import GenericMeta

    ABCMeta = GenericMeta  # type: ignore

except ImportError:
    pass
# Todo: Delete above try/except when dropping support for Python 3.6.


PipeableExpression = Union["PipelineExpression", "PipeableMetaclass"]


class PipelineExpression(object):
    """
    Implements a left-to-right association between two objects.
    """

    def __init__(self, left: PipeableExpression, right: PipeableExpression):
        self.left = left
        self.right = right

    def __or__(self, other: PipeableExpression) -> PipeableExpression:
        return PipelineExpression(self, other)

    def __iter__(self) -> Iterator["PipeableMetaclass"]:
        for term in (self.left, self.right):
            if isinstance(term, PipelineExpression):
                for item in term:
                    yield item
            else:
                assert isinstance(term, PipeableMetaclass), term
                yield term


class PipeableMetaclass(ABCMeta):
    """
    Meta class for pipeable classes.
    """

    def __or__(self, other: PipeableExpression) -> PipelineExpression:
        """
        Implements bitwise or operator '|' as a pipe between pipeable classes.
        """
        return PipelineExpression(self, other)

    def __iter__(self) -> Iterator["PipeableMetaclass"]:
        yield self


class Pipeable(metaclass=PipeableMetaclass):
    """
    Base class for pipeable classes.
    """
