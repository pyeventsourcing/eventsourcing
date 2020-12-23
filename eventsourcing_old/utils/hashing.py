import hashlib
import os

from eventsourcing.utils.transcoding import ObjectJSONEncoder

SALT_FOR_DATA_INTEGRITY = os.getenv("SALT_FOR_DATA_INTEGRITY", "")


def hash_object(json_encoder: ObjectJSONEncoder, obj: dict) -> str:
    """
    Calculates SHA-256 hash of JSON encoded 'obj'.

    :param json_encoder: JSON encoder object.
    :param obj: Object to be hashed.
    :return: SHA-256 as hexadecimal string.
    :rtype str
    """
    s = json_encoder.encode((obj, SALT_FOR_DATA_INTEGRITY))
    return hashlib.sha256(s).hexdigest()
