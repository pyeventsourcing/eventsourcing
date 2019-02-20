from abc import ABCMeta


class PipelineExpression(object):
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
    def __or__(self, other):
        return PipelineExpression(self, other)


class Pipeable(metaclass=PipeableMetaclass):
    pass
