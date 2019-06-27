import importlib

from eventsourcing.exceptions import TopicResolutionError


def get_topic(domain_class):
    """Returns a string describing a class.

    Args:
        domain_class: A class.

    Returns:
        A string describing the class.
    """
    return domain_class.__module__ + '#' + getattr(domain_class, '__qualname__', domain_class.__name__)


# Todo: Document this.
substitutions = {}


def resolve_topic(topic):
    """Return class described by given topic.

    Args:
        topic: A string describing a class.

    Returns:
        A class.

    Raises:
        TopicResolutionError: If there is no such class.
    """
    # Substitute one topic for another, if so defined.
    #  - this allows classes to be moved and renamed
    topic = substitutions.get(topic, topic)

    # Partition topic into module and class names.
    module_name, _, class_name = topic.partition('#')

    # Import the module.
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise TopicResolutionError("{}: {}".format(topic, e))

    # Identify the class.
    try:
        cls = resolve_attr(module, class_name)
    except AttributeError as e:
        raise TopicResolutionError("{}: {}".format(topic, e))
    return cls


def resolve_attr(obj, path):
    """A recursive version of getattr for navigating dotted paths.

    Args:
        obj: An object for which we want to retrieve a nested attribute.
        path: A dot separated string containing zero or more attribute names.

    Returns:
        The attribute referred to by obj.a1.a2.a3...

    Raises:
        AttributeError: If there is no such attribute.
    """
    if not path:
        return obj
    head, _, tail = path.partition('.')
    head_obj = getattr(obj, head)
    return resolve_attr(head_obj, tail)
