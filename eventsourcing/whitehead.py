from typing import Iterable, NamedTuple, TypeVar


class Event(object):
    """
    "I shall use the term 'event' in the more general sense
    of a nexus of actual occasions, inter-related in some
    determinate fashion in one extensive quantum. An actual
    occasion is the limiting type of an event with only one
    member."

    Alfred North Whitehead, 1929
    """


class ActualOccasion(Event):
    """
    "'Actual entities' -- also termed 'actual occasions' -- are the final real things
    of which the world is made up. There is no going behind actual entities
    to find anything more real."

    "Just as 'potentiality for process' is the meaning of the more general term
    'entity' or 'thing'; so 'decision' is the additional meaning imported by the
    word 'actual' into the phrase 'actual entity'. 'Actuality' is the decision
    amid 'potentiality'. It represents stubborn fact which cannot be evaded."

    "Actual entities perish, but do not change; they are what they are."

    Alfred North Whitehead, 1929
    """


class EnduringObject(Event):
    """
    "The notions of 'social order' and of 'personal order' cannot be omitted
    from this preliminary sketch. A 'society' in the sense in which that term
    is here used, is a nexus with social order; and an 'enduring object' or
    'enduring creature' is a society whose social order has taken the special
    form of 'personal order.'"

    "A nexus enjoys 'personal order' when (a) it is a 'society' and when
    the genetic relatedness of its members orders these members 'serially'."

    Alfred North Whitehead, 1929
    """


T = TypeVar("T")

TEvent = TypeVar("TEvent", bound=ActualOccasion)
TEntity = TypeVar("TEntity", bound=EnduringObject)
SEntity = TypeVar("SEntity", bound=EnduringObject)

IterableOfEvents = Iterable[ActualOccasion]
IterableOfItems = Iterable[NamedTuple]
