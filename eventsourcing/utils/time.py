import datetime

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
