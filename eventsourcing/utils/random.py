from base64 import b64encode, b64decode

import os


def encode_random_bytes(num_bytes):
    """
    Generates random bytes, encoded as Base64 unicode string.

    :param int num_bytes: Number of random bytes to generate.
    :return: Random bytes of specified length, encoded as Base64 unicode string.
    :type: str
    """
    return encode_bytes(random_bytes(num_bytes))


def random_bytes(num_bytes):
    """
    Generates random bytes.

    :param int num_bytes: Number of random bytes to generate.
    :return: Random bytes of specified length.
    :type: bytes
    """
    return os.urandom(num_bytes)


def encode_bytes(bytes):
    """
    Encodes bytes as Base64 unicode string.

    """
    return b64encode(bytes).decode("utf-8")


def decode_bytes(s):
    """
    Decodes bytes from Base64 encoded unicode string.

    :param str s: Base64 string.
    :returns: Bytes that were encoded with Base64.
    :rtype: bytes
    """
    return b64decode(s.encode("utf-8"))
