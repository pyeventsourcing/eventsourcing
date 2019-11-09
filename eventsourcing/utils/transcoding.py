import datetime
from collections import deque
from decimal import Decimal
from enum import Enum
from functools import singledispatch, wraps
from inspect import isfunction
from json import JSONDecoder, JSONEncoder
from types import FunctionType, MethodType
from uuid import UUID

import dateutil.parser

from eventsourcing.utils.topic import get_topic, resolve_topic

JSON_SEPARATORS = (",", ":")


def encoderpolicy(arg=None):
    """
    Singledispatch Decorator for encoder default method.

    Allows default behaviour to be built up from methods
    registered for different event classes, rather than
    chain of isinstance() calls in a long if-else block.
    """

    def _mutator(func):
        wrapped = singledispatch(func)

        @wraps(wrapped)
        def wrapper(*args, **kwargs):
            obj = kwargs.get("obj") or args[-1]
            return wrapped.dispatch(type(obj))(*args, **kwargs)

        wrapper.register = wrapped.register

        return wrapper

    assert isfunction(arg), arg
    return _mutator(arg)


class ObjectJSONEncoder(JSONEncoder):
    def __init__(self, sort_keys=True, *args, **kwargs):
        super(ObjectJSONEncoder, self).__init__(sort_keys=sort_keys, *args, **kwargs)

    def iterencode(self, o, _one_shot=False):
        if isinstance(o, tuple):
            o = {"__tuple__": {"topic": (get_topic(o.__class__)), "state": (list(o))}}
        return super(ObjectJSONEncoder, self).iterencode(o, _one_shot=_one_shot)

    @encoderpolicy
    def default(self, obj):
        return JSONEncoder.default(self, obj)

    @default.register(UUID)
    def _(self, obj):
        return {"UUID": obj.hex}

    @default.register(datetime.datetime)
    def _(self, obj):
        return {"ISO8601_datetime": obj.strftime("%Y-%m-%dT%H:%M:%S.%f%z")}

    @default.register(datetime.date)
    def _(self, obj):
        return {"ISO8601_date": obj.isoformat()}

    @default.register(datetime.time)
    def _(self, obj):
        return {"ISO8601_time": obj.strftime("%H:%M:%S.%f")}

    @default.register(Decimal)
    def _(self, obj):
        return {"__decimal__": str(obj)}

    @default.register(Enum)
    def _(self, obj):
        return {
            "__enum__": {
                "topic": get_topic(type(obj)),
                "name": obj.name,
            }
        }

    @default.register(set)
    def _(self, obj):
        return {"__set__": sorted(list(obj))}

    @default.register(deque)
    def _(self, obj):
        if list(obj):
            raise ValueError("Only empty deques are supported at the moment")
        else:
            return {"__deque__": []}

    @default.register(object)
    def _(self, obj):
        if hasattr(obj, "__slots__"):
            topic = get_topic(obj.__class__)
            state = {k: getattr(obj, k) for k in obj.__slots__}
            return {"__class__": {"topic": topic, "state": state}}
        elif hasattr(obj, "__dict__"):
            topic = get_topic(obj.__class__)
            state = obj.__dict__.copy()
            return {"__class__": {"topic": topic, "state": state}}
        else:
            return JSONEncoder.default(self, obj)

    @default.register(type)
    def _(self, obj):
        return {"__type__": get_topic(obj)}

    @default.register(MethodType)
    def _(self, obj):
        return JSONEncoder.default(self, obj)

    @default.register(FunctionType)
    def _(self, obj):
        return JSONEncoder.default(self, obj)


class ObjectJSONDecoder(JSONDecoder):
    def __init__(self, object_hook=None, **kwargs):
        super(ObjectJSONDecoder, self).__init__(
            object_hook=object_hook or self.from_jsonable, **kwargs
        )

    @classmethod
    def from_jsonable(cls, d):
        if "ISO8601_datetime" in d:
            return cls._decode_datetime(d)
        elif "ISO8601_date" in d:
            return cls._decode_date(d)
        elif "UUID" in d:
            return cls._decode_uuid(d)
        elif "__decimal__" in d:
            return cls._decode_decimal(d)
        elif "ISO8601_time" in d:
            return cls._decode_time(d)
        elif "__type__" in d:
            return cls._decode_type(d)
        elif "__class__" in d:
            return cls._decode_object(d)
        elif "__tuple__" in d:
            return cls._decode_tuple(d)
        elif "__deque__" in d:
            return deque([])
        elif "__set__" in d:
            return set(d["__set__"])
        elif "__enum__" in d:
            return cls._decode_enum(d)
        return d

    @classmethod
    def _decode_time(cls, d):
        hour, minute, seconds = d["ISO8601_time"].split(":")
        second, microsecond = seconds.split(".")
        return datetime.time(int(hour), int(minute), int(second), int(microsecond))

    @classmethod
    def _decode_decimal(cls, d):
        return Decimal(d["__decimal__"])

    @staticmethod
    def _decode_date(d):
        return datetime.datetime.strptime(d["ISO8601_date"], "%Y-%m-%d").date()

    @staticmethod
    def _decode_datetime(d):
        return dateutil.parser.parse(d["ISO8601_datetime"])

    @staticmethod
    def _decode_uuid(d):
        return UUID(d["UUID"])

    @staticmethod
    def _decode_type(d):
        return resolve_topic(d["__type__"])

    @staticmethod
    def _decode_object(d):
        topic = d["__class__"]["topic"]
        state = d["__class__"]["state"]
        obj_class = resolve_topic(topic)
        obj = object.__new__(obj_class)
        if hasattr(obj, "__dict__"):
            obj.__dict__.update(state)
        else:
            for k, v in state.items():
                object.__setattr__(obj, k, v)
        return obj

    @staticmethod
    def _decode_tuple(d):
        topic = d["__tuple__"]["topic"]
        state = d["__tuple__"]["state"]
        tuple_type = resolve_topic(topic)
        if topic == "builtins#tuple":
            # For standard tuple objects.
            obj = tuple_type(state)
        else:
            # For NamedTuple objects.
            obj = tuple_type(*state)
        return obj

    @staticmethod
    def _decode_enum(d):
        topic = d["__enum__"]["topic"]
        name = d["__enum__"]["name"]
        enum = resolve_topic(topic)
        return getattr(enum, name)

