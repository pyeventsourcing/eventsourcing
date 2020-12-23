import importlib
from typing import Any, Dict, Type

from eventsourcing.domain.model.versioning import Upcastable
from eventsourcing.exceptions import TopicResolutionError
from eventsourcing.whitehead import T


def get_topic(domain_class: type) -> str:
    """
    Returns a string describing a class.

    :param domain_class: A class.
    :returns: A string describing the class.
    """
    return (
        domain_class.__module__
        + "#"
        + getattr(domain_class, "__qualname__", domain_class.__name__)
    )


# Todo: Write documentation for this feature (versioning...).

substitutions: Dict[str, str] = {}


def resolve_topic(topic: str) -> Any:
    """
    Resolves topic to the object it references.

    :param topic: A string describing a code object (e.g. an object class).
    :raises TopicResolutionError: If there is no such class.
    :return: Code object that the topic references.
    """
    # Substitute one topic for another, if so defined.
    #  - this allows classes to be moved and renamed
    topic = substitutions.get(topic, topic)

    # Partition topic into module and class names.
    module_name, _, class_name = topic.partition("#")

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


def resolve_attr(obj: Any, path: str) -> Any:
    """
    A recursive version of getattr for navigating dotted paths.

    :param obj: An object for which we want to retrieve a nested attribute.
    :param path: A dot separated string containing zero or more attribute names.
    :raises AttributeError: If there is no such attribute.
    :return: The attribute referred to by the path.
    """
    if not path:
        return obj
    head, _, tail = path.partition(".")
    head_obj = getattr(obj, head)
    return resolve_attr(head_obj, tail)


def reconstruct_object(obj_class: Type[T], obj_state: Dict[str, Any]) -> T:
    """
    Reconstructs object from given class and state.

    :param obj_class: Class of object to be reconstructed.
    :param obj_state: State of object to be reconstructed.
    :return: Reconstructed object.
    """
    if issubclass(obj_class, Upcastable):
        # Upcast the recorded state using the given class.
        obj_state = obj_class.__upcast_state__(obj_state)

    # Reconstruct the object class instance from the state.
    obj = object.__new__(obj_class)
    obj.__dict__.update(obj_state)
    return obj
