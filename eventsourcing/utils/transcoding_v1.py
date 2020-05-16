import datetime
from base64 import b64decode, b64encode
from collections import deque
from decimal import Decimal
from enum import Enum
from functools import singledispatch, wraps
from inspect import isfunction
from json import JSONDecoder, JSONEncoder
from types import FunctionType, MethodType
from uuid import UUID

import dateutil.parser

from eventsourcing.exceptions import EncoderTypeError
from eventsourcing.utils.topic import get_topic, resolve_topic

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
    def encode(self, o):
        return super(ObjectJSONEncoder, self).encode(o).encode("utf8")

    def iterencode(self, o, _one_shot=False):
        if isinstance(o, tuple):
            o = {"__tuple__": {"topic": (get_topic(o.__class__)), "state": (list(o))}}
        return super(ObjectJSONEncoder, self).iterencode(o, _one_shot=_one_shot)

    def default(self, obj):
        try:
            return encoder(obj)
        except EncoderTypeError:
            return JSONEncoder.default(self, obj)


@encoderpolicy
def encoder(obj):
    """Extensible encoder function."""


class ObjectJSONDecoder(JSONDecoder):
    def __init__(self, object_hook=None, **kwargs):
        super(ObjectJSONDecoder, self).__init__(
            object_hook=object_hook or decoder, **kwargs
        )


@decoderpolicy
def decoder(d):
    """Extensible decoder function."""


@encoder.register(bytes)
def encode_bytes(obj):
    return {"__bytes__": b64str_from_bytes(obj)}


@encoder.register(type)
def encode_type(obj):
    return {"__type__": get_topic(obj)}


@encoder.register(MethodType)
def encode_method(obj):
    raise EncoderTypeError(obj)


@encoder.register(FunctionType)
def encode_function(obj):
    raise EncoderTypeError(obj)


@decoder.register("__type__")
def decode_type(d):
    return resolve_topic(d["__type__"])


@encoder.register(object)
def encode_object(obj):
    if hasattr(obj, "__slots__"):
        topic = get_topic(obj.__class__)
        state = {k: getattr(obj, k) for k in obj.__slots__}
        return {"__class__": {"topic": topic, "state": state}}
    elif hasattr(obj, "__dict__"):
        topic = get_topic(obj.__class__)
        state = obj.__dict__.copy()
        return {"__class__": {"topic": topic, "state": state}}
    else:
        raise EncoderTypeError(obj)


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


@encoder.register(deque)
def encode_deque(obj):
    return {"__deque__": {"topic": get_topic(type(obj)), "values": list(obj)}}


@decoder.register("__deque__")
def decode_deque(d):
    topic = d["__deque__"]["topic"]
    values = d["__deque__"]["values"]
    deque = resolve_topic(topic)
    return deque(values)


@decoder.register("__tuple__")
def decode_tuple(d):
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


@encoder.register(set)
def encode_set(obj):
    return {"__set__": sorted(list(obj))}


@decoder.register("__set__")
def decode_set(d):
    return set(d["__set__"])


@decoder.register("__bytes__")
def decode_bytes(d):
    return bytes_from_b64str(d["__bytes__"])


def b64str_from_bytes(value: bytes) -> str:
    return b64encode(value).decode("utf8")


def bytes_from_b64str(value):
    return b64decode(value.encode("utf8"))
