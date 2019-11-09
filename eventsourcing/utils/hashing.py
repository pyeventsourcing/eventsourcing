import hashlib
import os

SALT_FOR_DATA_INTEGRITY = os.getenv("SALT_FOR_DATA_INTEGRITY", "")


def hash_object(json_encoder, obj):
    """
    Calculates SHA-256 hash of JSON encoded 'obj'.

    :param obj: Object to be hashed.
    :return: SHA-256 as hexadecimal string.
    :rtype str
    """
    s = json_encoder.encode((obj, SALT_FOR_DATA_INTEGRITY))
    return hashlib.sha256(s.encode()).hexdigest()
