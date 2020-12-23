from typing import Dict

from eventsourcing.whitehead import Event


class Upcastable(Event):
    """
    For things that are upcastable.

    http://code.fed.wiki.org/view/wyatt-software/view/remote-database-schema-migration

    "I was sure that we could not get the schema for WyCash Plus right
    on the first try. I was familiar with Smaltalk-80's object migration
    mechanisms. I designed a version that could serve us in a commercial
    software distribution environment.

    "I chose to version each class independently and write that as a
    sequential integer in the serialized versions. Objects would be
    mutated to the current version on read. We supported all versions
    we ever had forever.

    "I recorded mutation vectors for each version to the present. These could
    add, remove and reorder fields within an object. One-off mutation methods
    handled the rare case where the vectors were not enough description.

    "We shipped migrations to our customers with each release to be performed
    on their own machines when needed without any intervention."

    Ward Cunningham
    """

    __class_version__ = 0

    def __init__(self):
        if type(self).__class_version__ > 0:
            self.__dict__["__class_version__"] = type(self).__class_version__
        super(Upcastable, self).__init__()

    @classmethod
    def __upcast_state__(cls, obj_state: Dict) -> Dict:
        """
        Upcasts obj_state from the version of the class when the object
        state was recorded, to be compatible with current version of the class.
        """
        class_version = obj_state.get("__class_version__", 0)
        while class_version < cls.__class_version__:
            obj_state = cls.__upcast__(obj_state, class_version)
            class_version += 1
            obj_state["__class_version__"] = class_version
        return obj_state

    @classmethod
    def __upcast__(cls, obj_state: Dict, class_version: int) -> Dict:
        """
        Must be overridden in domain event classes that set class
        attribute '__class_version__' to a positive value.

        This method is expected to upcast obj_state from method arg
        'class_version' to the next version, and return obj_state.

        One style of implementation is an if-else block, in which the
        conditional expressions match on the value of 'class_version'.

        The implementation of this method must support upcasting each version
        of the class from 0 to one less than the current version.
        For example: a domain class with "__class_version__ = 1" will
        need to support upcasting "class_version == 0" to version 1; and a
        domain class with "__class_version__ = 2" will need to support both
        upcasting "class_version == 0" to version 1, and also upcasting
        "class_version == 1" to version 2.

        To support backward compatibility, the recorded state of old
        versions of an event class will need to be upcast to work with new
        versions of the software. Commonly, this involves supplying
        default values for attributes missing on old versions of events,
        after an event class has been changed by adding a new attribute.

        In a situation where a new version of an event class needs to be used
        by existing software, it would be necessary also to support forward
        compatibility. Examples of this situation include the situation
        of deploying with rolling updates, and the situation where consumers
        would receive and attempt to handle the new version of the event but
        cannot be updated before the new event class version is deployed.

        To support forward compatibility, it is necessary to restrict changes
        to be merely additive: either adding new attributes to an event, or
        adding new behaviours to the type of an existing attribute. Event
        attributes shouldn't be removed (or renamed), existing attributes
        should not have aspects of their behaviour removed, and the semantics
        of an existing attribute should not change. If the type of an attribute
        value is changed, the new type should substitutable for the old type.
        The old software will then simply ignore new attributes, and it will
        simply ignore new aspects of new types of value.

        For example, the type of an attribute value can be changed to use a
        subtype of the previous attribute value type. The possible range of a
        value can be reduced when changing the type of an attribute value, since
        all the values of the new type will be  supported by the old software.

        Increasing the possible range of a value will introduce values that
        cannot be used by the old software, and changing the type of an
        attribute value to a supertype will remove behaviour that the old
        software may depend on.

        Of course, if the old software doesn't in fact depend on aspects
        that are removed, then those aspects can be removed without actually
        breaking anything.

        If backward and forward compatibility is required, and it is felt
        that an event class needs to be changed that would cause an attribute
        to be removed or the type of an attribute to be more general, or the
        range of values of an attribute to increase, then according to Greg
        Young's book 'Versioning in an Event Sourced System' it is better to
        to add a new event type. However, if the old software would break
        because this new event type is not supported, then supporting
        forward compatibility would be elusive.

        In summary, supporting forward compatibility restricts model changes to
        adding attributes to existing model classes (which implies the versioned
        event class' upcast method will supply default values when upcasting
        the state of old versions of the event).
        """
        raise NotImplementedError(cls)
