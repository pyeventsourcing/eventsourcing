from six import with_metaclass


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


class PipeableMetaclass(type):
    def __or__(self, other):
        return PipelineExpression(self, other)


class Pipeable(with_metaclass(PipeableMetaclass)):
    pass
