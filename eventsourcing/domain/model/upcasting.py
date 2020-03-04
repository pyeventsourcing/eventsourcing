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
            self.__dict__['__class_version__'] = type(self).__class_version__
        super(Upcastable, self).__init__()

    @classmethod
    def __upcast_state__(cls, obj_state: Dict) -> Dict:
        """
        Upcasts obj_state from the version of the class when the object
        state was recorded, to be compatible with current version of the class.
        """
        class_version = obj_state.get('__class_version__', 0)
        while class_version < cls.__class_version__:
            obj_state = cls.__upcast__(obj_state, class_version)
            class_version += 1
            obj_state['__class_version__'] = class_version
        return obj_state

    @classmethod
    def __upcast__(cls, obj_state: Dict, class_version: int) -> Dict:
        raise NotImplemented()
