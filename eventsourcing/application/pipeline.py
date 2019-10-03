from abc import ABCMeta


class PipelineExpression(object):
    """
    Implements a left-to-right association between two objects.
    """

    def __init__(self, left, right):
        self.left = left
        self.right = right

    def __or__(self, other):
        return PipelineExpression(self, other)

    def __iter__(self):
        for term in (self.left, self.right):
            if isinstance(term, PipelineExpression):
                for item in term:
                    yield item
            else:
                assert issubclass(term, Pipeable), term
                yield term


class PipeableMetaclass(ABCMeta):
    """
    Meta class for pipeable classes.
    """

    def __or__(self, other):
        """
        Implements bitwise or operator '|' as a pipe between pipeable classes.
        """
        return PipelineExpression(self, other)

    def __iter__(self):
        yield self


class Pipeable(metaclass=PipeableMetaclass):
    """
    Base class for pipeable classes.
    """
