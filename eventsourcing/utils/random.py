import os
from base64 import b64decode, b64encode


def encoded_random_bytes(num_bytes: int) -> str:
    """
    Generates random bytes, encoded as Base64 unicode string.

    :param num_bytes: Number of random bytes to generate.
    :return: Random bytes of specified length, encoded as Base64 unicode string.
    """
    return encode_bytes(random_bytes(num_bytes))


encode_random_bytes = encoded_random_bytes  # Backward compatibility with <= 7.2.9999.


def random_bytes(num_bytes: int) -> bytes:
    """
    Generates random bytes.

    :param num_bytes: Number of random bytes to generate.
    :return: Random bytes of specified length.
    :type: bytes
    """
    return os.urandom(num_bytes)


def encode_bytes(value: bytes) -> str:
    """
    Encodes value as Base64 unicode string.

    :param value: Bytes to be encoded.
    """
    return b64encode(value).decode("utf-8")


def decode_bytes(value: str) -> bytes:
    """
    Decodes bytes from Base64 encoded unicode string.

    :param str value: Base64 string.
    :returns: Bytes that were encoded with Base64.
    :rtype: bytes
    """
    return b64decode(value.encode("utf-8"))
