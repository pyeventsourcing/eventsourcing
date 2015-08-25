import datetime


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).timestamp()
