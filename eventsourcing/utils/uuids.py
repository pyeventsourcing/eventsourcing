import uuid


def uuid_from_application_name(application_name):
    return uuid_from_uri('eventsourcing:///applications/{}'.format(application_name))

def uuid_from_uri(uri):
    return uuid.uuid5(uuid.NAMESPACE_URL, uri.encode('utf8') if bytes == str else uri)
