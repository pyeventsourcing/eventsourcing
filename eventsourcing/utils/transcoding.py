import datetime
from decimal import Decimal
from json import JSONDecoder, JSONEncoder, dumps, loads
from uuid import UUID

import dateutil.parser

from eventsourcing.utils.topic import get_topic, resolve_topic
from collections import deque


class ObjectJSONEncoder(JSONEncoder):

    def __init__(self, sort_keys=True, *args, **kwargs):
        super(ObjectJSONEncoder, self).__init__(sort_keys=sort_keys, *args, **kwargs)

    def default(self, obj):
        if isinstance(obj, UUID):
            return {'UUID': obj.hex}
        elif isinstance(obj, datetime.datetime):
            return {'ISO8601_datetime': obj.strftime('%Y-%m-%dT%H:%M:%S.%f%z')}
        elif isinstance(obj, datetime.date):
            return {'ISO8601_date': obj.isoformat()}
        elif isinstance(obj, datetime.time):
            return {'ISO8601_time': obj.strftime('%H:%M:%S.%f')}
        elif isinstance(obj, Decimal):
            return {
                '__decimal__': str(obj),
            }
        elif hasattr(obj, '__class__') and hasattr(obj, '__dict__'):
            topic = get_topic(obj.__class__)
            state = obj.__dict__.copy()
            return {
                '__class__': {
                    'topic': topic,
                    'state': state,
                }
            }
        elif isinstance(obj, deque):
            assert list(obj) == []
            return {'__deque__': []}

        # Let the base class default method raise the TypeError.
        return JSONEncoder.default(self, obj)


class ObjectJSONDecoder(JSONDecoder):
    def __init__(self, object_hook=None, **kwargs):
        super(ObjectJSONDecoder, self).__init__(object_hook=object_hook or self.from_jsonable, **kwargs)

    @classmethod
    def from_jsonable(cls, d):
        if 'ISO8601_datetime' in d:
            return cls._decode_datetime(d)
        elif 'ISO8601_date' in d:
            return cls._decode_date(d)
        elif 'UUID' in d:
            return cls._decode_uuid(d)
        elif '__decimal__' in d:
            return cls._decode_decimal(d)
        elif 'ISO8601_time' in d:
            return cls._decode_time(d)
        elif '__class__' in d:
            return cls._decode_object(d)
        elif '__deque__' in d:
            return deque([])
        return d

    @classmethod
    def _decode_time(cls, d):
        hour, minute, seconds = d['ISO8601_time'].split(':')
        second, microsecond = seconds.split('.')
        return datetime.time(int(hour), int(minute), int(second), int(microsecond))

    @classmethod
    def _decode_decimal(cls, d):
        return Decimal(d['__decimal__'])

    @staticmethod
    def _decode_date(d):
        return datetime.datetime.strptime(d['ISO8601_date'], '%Y-%m-%d').date()

    @staticmethod
    def _decode_datetime(d):
        return dateutil.parser.parse(d['ISO8601_datetime'])

    @staticmethod
    def _decode_uuid(d):
        return UUID(d['UUID'])

    @staticmethod
    def _decode_object(d):
        topic = d['__class__']['topic']
        state = d['__class__']['state']
        obj_class = resolve_topic(topic)
        obj = object.__new__(obj_class)
        obj.__dict__.update(state)
        return obj


def json_dumps(obj, cls):
    return dumps(
        obj,
        separators=(',', ':'),
        sort_keys=True,
        cls=cls,
    )


def json_loads(s, cls):
    return loads(s, cls=cls)
