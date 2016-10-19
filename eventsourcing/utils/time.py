import datetime
from uuid import UUID

import six

if hasattr(datetime, 'timezone'):
    utc_timezone = datetime.timezone.utc
else:
    from datetime import tzinfo, timedelta

    class UTC(tzinfo):
        def utcoffset(self, date_time):
            return timedelta(0)

        def dst(self, date_time):
            return timedelta(0)
    utc_timezone = UTC()


def utc_now():
    now_datetime = datetime.datetime.now(utc_timezone)
    try:
        now_timestamp = now_datetime.timestamp()
    except AttributeError:
        now_timestamp = (now_datetime - datetime.datetime(1970, 1, 1, tzinfo=utc_timezone)).total_seconds()
    return now_timestamp


def timestamp_from_uuid(uuid_arg):
    """
    Return a floating point unix timestamp to 6 decimal places.

    :param uuid_arg:
    :return: Unix timestamp in seconds, with microsecond precision.
    :rtype: float
    """
    return timestamp_long_from_uuid(uuid_arg) / 1e7


def timestamp_long_from_uuid(uuid_arg):
    return time_from_uuid(uuid_arg) - 0x01B21DD213814000


def time_from_uuid(uuid_arg):
    if isinstance(uuid_arg, six.string_types):
        uuid_arg = UUID(uuid_arg)
    assert isinstance(uuid_arg, UUID)
    uuid_time = uuid_arg.time
    return uuid_time
