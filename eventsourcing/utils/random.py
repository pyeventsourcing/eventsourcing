from base64 import b64encode, b64decode

import os


def encode_random_bytes(num_bytes):
    """Generates random bytes, encoded as Base64 unicode string."""
    return b64encode(os.urandom(num_bytes)).decode('utf-8')


def decode_random_bytes(s):
    """Returns bytes, decoded from Base64 encoded unicode string."""
    return b64decode(s.encode('utf-8'))
