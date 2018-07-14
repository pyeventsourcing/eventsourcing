import uuid


def uuid_from_uri(uri):
    return uuid.uuid5(uuid.NAMESPACE_URL, uri.encode('utf8') if bytes == str else uri)
