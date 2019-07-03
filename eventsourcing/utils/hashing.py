import hashlib
import os

from eventsourcing.utils.transcoding import json_dumps

SALT_FOR_DATA_INTEGRITY = os.getenv('SALT_FOR_DATA_INTEGRITY', '')


def hash_object(json_encoder_class, obj):
    """
    Calculates SHA-256 hash of JSON encoded 'obj'.

    :param obj: Object to be hashed.
    :return: SHA-256 as hexadecimal string.
    :rtype str
    """
    s = json_dumps(
        (obj, SALT_FOR_DATA_INTEGRITY),
        cls=json_encoder_class,
    )
    return hashlib.sha256(s.encode()).hexdigest()
