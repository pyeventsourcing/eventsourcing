import uuid


def uuid_from_url(url):
    return uuid.uuid5(uuid.NAMESPACE_URL, url.encode('utf8') if bytes == str else url)


def uuid_from_application_name(application_name):
    return uuid_from_url('eventsourcing:///applications/{}'.format(application_name))
