import datetime
from base64 import b64decode, b64encode
from collections import deque
from decimal import Decimal
from enum import Enum
from functools import singledispatch, wraps
from inspect import isfunction
from json import JSONDecoder, JSONEncoder
from modulefinder import Module
from types import FunctionType, MethodType
from typing import Optional
from uuid import UUID

import dateutil.parser

from eventsourcing.exceptions import EncoderTypeError
from eventsourcing.utils.topic import get_topic, resolve_topic

try:
    import orjson
except ImportError:
    orjson: Optional[Module] = None  # type: ignore


JSON_SEPARATORS = (",", ":")


def encoderpolicy(arg=None):
    """
    Decorator for encoder policy.

    Allows default behaviour to be built up from methods
    registered for different types of things, rather than
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


def decoderpolicy(arg=None):
    """
    Decorator for decoder policy.

    Allows default behaviour to be built up from methods
    registered for different named keys, rather than
    chain of "in dict" queries in a long if-else block.
    """

    def _mutator(func):
        wrapped = func

        decoder_map = {}

        @wraps(wrapped)
        def wrapper(*args, **kwargs):

            d = kwargs.get("d") or args[-1]
            keys = list(d.keys())

            if len(keys) == 1:
                try:
                    decoder_func = decoder_map[keys[0]]
                except KeyError:
                    return d
                else:
                    return decoder_func(d)
            else:
                return d

        def register(key):
            def decorator(decoder_func):
                decoder_map[key] = decoder_func
                return decoder_func

            return decorator

        wrapper.register = register

        return wrapper

    assert isfunction(arg), arg
    return _mutator(arg)


class ObjectJSONEncoder(JSONEncoder):
    def __init__(self, sort_keys=False):
        super().__init__(sort_keys=sort_keys, separators=JSON_SEPARATORS)

    def encode(self, o):
        o = self.encode_object(o)
        if self.sort_keys is True or orjson is None:
            return super(ObjectJSONEncoder, self).encode(o).encode("utf8")
        else:
            return orjson.dumps(o)

    def encode_object(self, o):
        return self.encode_container(encoder(o))

    @encoderpolicy
    def encode_container(self, o):
        return o

    @encode_container.register(dict)
    def encode_dict(self, o):
        if type(o) == dict:
            return self.encode_dict_state(o)
        else:
            return {
                "__dict__": {
                    "topic": get_topic(o.__class__),
                    "state": self.encode_dict_state(o),
                }
            }

    def encode_dict_state(self, o):
        return {k: self.encode_object(v) for (k, v) in o.items()}

    @encode_container.register(tuple)
    def encode_tuple(self, o):
        if type(o) == tuple:
            return {"__tuple__": self.encode_object(list(o))}
        else:
            return {
                "__tuple__": {
                    "state": self.encode_object(list(o)),
                    "topic": get_topic(o.__class__),
                }
            }

    @encode_container.register(list)
    def encode_list(self, o):
        if type(o) == list:
            return [self.encode_object(i) for i in o]
        else:
            return {
                "__list__": {
                    "state": [self.encode_object(i) for i in o],
                    "topic": get_topic(o.__class__),
                }
            }

    @encode_container.register(set)
    def encode_set(self, o):
        if type(o) == set:
            return {"__set__": self.encode_iterable(o)}
        else:
            return {
                "__set__": {
                    "state": self.encode_iterable(o),
                    "topic": get_topic(o.__class__),
                }
            }

    def encode_iterable(self, o):
        return self.encode_object(self.sort_keys and sorted(o) or list(o))

    @encode_container.register(frozenset)
    def encode_frozenset(self, o):
        if type(o) == frozenset:
            return {"__frozenset__": self.encode_iterable(o)}
        else:
            return {
                "__frozenset__": {
                    "state": self.encode_iterable(o),
                    "topic": get_topic(o.__class__),
                }
            }

    @encode_container.register(deque)
    def encode_deque(self, o):
        if type(o) == deque:
            return {"__deque__": self.encode_object(list(o))}
        else:
            return {
                "__deque__": {
                    "state": self.encode_object(list(o)),
                    "topic": get_topic(o.__class__),
                }
            }

    @encode_container.register(object)
    def encode_instance(self, o):
        if hasattr(o, "__slots__") and o.__slots__ != ():
            topic = get_topic(o.__class__)
            state = {k: self.encode_object(getattr(o, k)) for k in o.__slots__}
            return {"__class__": {"state": state, "topic": topic}}
        elif hasattr(o, "__dict__"):
            topic = get_topic(o.__class__)
            state = {k: self.encode_object(v) for k, v in o.__dict__.items()}
            return {"__class__": {"state": state, "topic": topic}}
        else:
            return o


@encoderpolicy
def encoder(o):
    return o


class ObjectJSONDecoder(JSONDecoder):
    def __init__(self, object_hook=None, **kwargs):
        super(ObjectJSONDecoder, self).__init__(
            object_hook=object_hook or decoder, **kwargs
        )


@decoderpolicy
def decoder(d):
    return d


@encoder.register(type)
def encode_type(o):
    return {"__type__": get_topic(o)}


@encoder.register(MethodType)
def encode_method(o):
    raise EncoderTypeError(o)


@encoder.register(FunctionType)
def encode_function(o):
    raise EncoderTypeError(o)


@decoder.register("__type__")
def decode_type(d):
    return resolve_topic(d["__type__"])


@decoder.register("__class__")
def decode_object(d):
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


@encoder.register(UUID)
def encode_uuid(obj):
    return {"UUID": obj.hex}


@decoder.register("UUID")
def decode_uuid(d):
    return UUID(d["UUID"])


@encoder.register(datetime.datetime)
def encode_datetime(obj):
    return {"ISO8601_datetime": obj.strftime("%Y-%m-%dT%H:%M:%S.%f%z")}


@decoder.register("ISO8601_datetime")
def decode_datetime(d):
    return dateutil.parser.parse(d["ISO8601_datetime"])


@encoder.register(datetime.date)
def encode_date(obj):
    return {"ISO8601_date": obj.isoformat()}


@decoder.register("ISO8601_date")
def decode_date(d):
    return datetime.datetime.strptime(d["ISO8601_date"], "%Y-%m-%d").date()


@encoder.register(datetime.time)
def encode_time(obj):
    return {"ISO8601_time": obj.strftime("%H:%M:%S.%f")}


@decoder.register("ISO8601_time")
def decode_time(d):
    hour, minute, seconds = d["ISO8601_time"].split(":")
    second, microsecond = seconds.split(".")
    return datetime.time(int(hour), int(minute), int(second), int(microsecond))


@encoder.register(Decimal)
def encode_decimal(obj):
    return {"__decimal__": str(obj)}


@decoder.register("__decimal__")
def decode_decimal(d):
    return Decimal(d["__decimal__"])


@encoder.register(Enum)
def encode_enum(obj):
    return {"__enum__": {"topic": get_topic(type(obj)), "name": obj.name}}


@decoder.register("__enum__")
def decode_enum(d):
    topic = d["__enum__"]["topic"]
    name = d["__enum__"]["name"]
    enum = resolve_topic(topic)
    return getattr(enum, name)


@decoder.register("__deque__")
def decode_deque(d):
    deque_data = d["__deque__"]
    if type(deque_data) == dict:
        topic = deque_data["topic"]
        try:
            state = deque_data["state"]
        except KeyError:
            state = deque_data["values"]

        deque_type = resolve_topic(topic)
        return deque_type(state)
    else:
        return deque(deque_data)


@decoder.register("__tuple__")
def decode_tuple(d):
    tuple_data = d["__tuple__"]
    if type(tuple_data) == dict:
        # For NamedTuple objects.
        topic = tuple_data["topic"]
        state = tuple_data["state"]
        tuple_type = resolve_topic(topic)
        obj = tuple_type(*state)
    else:
        # For standard tuple objects.
        obj = tuple(tuple_data)
    return obj


@decoder.register("__dict__")
def decode_dict(d):
    topic = d["__dict__"]["topic"]
    state = d["__dict__"]["state"]
    dict_type = resolve_topic(topic)
    return dict_type(state)


@decoder.register("__set__")
def decode_set(d):
    set_data = d["__set__"]
    if isinstance(set_data, dict):
        topic = set_data["topic"]
        state = set_data["state"]
        set_type = resolve_topic(topic)
        return set_type(state)
    else:
        return set(set_data)


@decoder.register("__frozenset__")
def decode_frozenset(d):
    set_data = d["__frozenset__"]
    if isinstance(set_data, dict):
        topic = set_data["topic"]
        state = set_data["state"]
        set_type = resolve_topic(topic)
        return set_type(state)
    else:
        return frozenset(set_data)


@encoder.register(bytes)
def encode_bytes(o):
    return {"__bytes__": b64str_from_bytes(o)}


@decoder.register("__bytes__")
def decode_bytes(d):
    return bytes_from_b64str(d["__bytes__"])


def b64str_from_bytes(value: bytes) -> str:
    return b64encode(value).decode("utf8")


def bytes_from_b64str(value):
    return b64decode(value.encode("utf8"))
