import datetime
from uuid import UUID, uuid5

from dateutil.relativedelta import relativedelta

from eventsourcing.domain.model.entity import AbstractEntityRepository, TimestampedVersionedEntity
from eventsourcing.domain.model.events import EventWithOriginatorID, EventWithTimestamp, Logged, publish
from eventsourcing.exceptions import RepositoryKeyError
from eventsourcing.utils.times import datetime_from_timestamp, decimaltimestamp, utc_timezone
from eventsourcing.utils.topic import get_topic

Namespace_Timebuckets = UUID('0d7ee297-a976-4c29-91ff-84ffc79d8155')

ONE_YEAR = relativedelta(years=1)
ONE_MONTH = relativedelta(months=1)
ONE_DAY = relativedelta(days=1)
ONE_HOUR = relativedelta(hours=1)
ONE_MINUTE = relativedelta(minutes=1)
ONE_SECOND = relativedelta(seconds=1)

BUCKET_SIZES = {
    'year': ONE_YEAR,
    'month': ONE_MONTH,
    'day': ONE_DAY,
    'hour': ONE_HOUR,
    'minute': ONE_MINUTE,
    'second': ONE_SECOND,
}


class Timebucketedlog(TimestampedVersionedEntity):
    class Event(TimestampedVersionedEntity.Event):
        """Supertype for events of time-bucketed log."""

    class Started(TimestampedVersionedEntity.Created, Event):
        pass

    class BucketSizeChanged(Event, TimestampedVersionedEntity.AttributeChanged):
        pass

    def __init__(self, name, bucket_size=None, **kwargs):
        super(Timebucketedlog, self).__init__(**kwargs)
        self._name = name
        self._bucket_size = bucket_size

    @property
    def name(self):
        return self._name

    @property
    def started_on(self):
        return self.__created_on__

    @property
    def bucket_size(self):
        return self._bucket_size

    def log_message(self, message):
        assert isinstance(message, str)
        bucket_id = make_timebucket_id(self.name, decimaltimestamp(), self.bucket_size)
        event = MessageLogged(
            originator_id=bucket_id,
            message=message,
        )
        publish(event)
        return event


class TimebucketedlogRepository(AbstractEntityRepository):
    def get_or_create(self, log_name, bucket_size):
        """
        Gets or creates a log.

        :rtype: Timebucketedlog
        """
        try:
            return self[log_name]
        except RepositoryKeyError:
            return start_new_timebucketedlog(log_name, bucket_size=bucket_size)


def start_new_timebucketedlog(name, bucket_size=None):
    if bucket_size is None:
        bucket_size = 'year'
    if bucket_size not in BUCKET_SIZES:
        raise ValueError("Bucket size '{}' not supported, must be one of: {}"
                         "".format(bucket_size, BUCKET_SIZES.keys()))
    event = Timebucketedlog.Started(
        originator_id=name,
        name=name,
        bucket_size=bucket_size,
        originator_topic=get_topic(Timebucketedlog)
    )
    entity = event.__mutate__()
    publish(event)
    return entity


class MessageLogged(EventWithTimestamp, EventWithOriginatorID, Logged):
    def __init__(self, message, originator_id):
        super(MessageLogged, self).__init__(originator_id=originator_id, message=message)

    @property
    def message(self):
        return self.__dict__['message']


def make_timebucket_id(log_id, timestamp, bucket_size):
    d = datetime_from_timestamp(timestamp)

    assert isinstance(d, datetime.datetime)
    if bucket_size.startswith('year'):
        boundary = '{:04}'.format(
            d.year
        )
    elif bucket_size.startswith('month'):
        boundary = '{:04}-{:02}'.format(
            d.year,
            d.month
        )
    elif bucket_size.startswith('day'):
        boundary = '{:04}-{:02}-{:02}'.format(
            d.year,
            d.month,
            d.day
        )
    elif bucket_size.startswith('hour'):
        boundary = '{:04}-{:02}-{:02}_{:02}'.format(
            d.year,
            d.month,
            d.day,
            d.hour
        )
    elif bucket_size.startswith('minute'):
        boundary = '{:04}-{:02}-{:02}_{:02}-{:02}'.format(
            d.year,
            d.month,
            d.day,
            d.hour,
            d.minute
        )
    elif bucket_size.startswith('second'):
        boundary = '{:04}-{:02}-{:02}_{:02}-{:02}-{:02}'.format(
            d.year,
            d.month,
            d.day,
            d.hour,
            d.minute,
            d.second
        )
    else:
        raise ValueError("Bucket size not supported: {}".format(bucket_size))
    return uuid5(Namespace_Timebuckets, log_id.hex + '_' + boundary)


def next_bucket_starts(timestamp, bucket_size):
    starts = bucket_starts(timestamp, bucket_size)
    duration = bucket_duration(bucket_size)
    return timestamp_from_datetime((starts + duration))


def previous_bucket_starts(timestamp, bucket_size):
    starts = bucket_starts(timestamp, bucket_size)
    duration = bucket_duration(bucket_size)
    return timestamp_from_datetime((starts - duration))


def bucket_starts(timestamp, bucket_size):
    dt = datetime_from_timestamp(timestamp)
    assert isinstance(dt, datetime.datetime)
    if bucket_size.startswith('year'):
        return datetime.datetime(dt.year, 1, 1, tzinfo=utc_timezone)
    elif bucket_size.startswith('month'):
        return datetime.datetime(dt.year, dt.month, 1, tzinfo=utc_timezone)
    elif bucket_size.startswith('day'):
        return datetime.datetime(dt.year, dt.month, dt.day, tzinfo=utc_timezone)
    elif bucket_size.startswith('hour'):
        return datetime.datetime(dt.year, dt.month, dt.day, dt.hour, tzinfo=utc_timezone)
    elif bucket_size.startswith('minute'):
        return datetime.datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, tzinfo=utc_timezone)
    elif bucket_size.startswith('second'):
        return datetime.datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=utc_timezone)
    else:
        raise ValueError("Bucket size not supported: {}".format(bucket_size))


def bucket_duration(bucket_size):
    try:
        return BUCKET_SIZES[bucket_size]
    except KeyError:
        raise ValueError("Bucket size not supported: {}. Must be one of: {}"
                         "".format(bucket_size, BUCKET_SIZES.keys()))


# Todo: Move to general utils?
def timestamp_from_datetime(dt):
    assert dt.tzinfo, "Datetime object does not have tzinfo"
    return dt.timestamp()
