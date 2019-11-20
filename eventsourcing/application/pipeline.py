from abc import ABCMeta
from typing import Iterator, Union

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
