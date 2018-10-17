from base64 import b64encode, b64decode

import os


def encode_random_bytes(num_bytes):
    """Generates random bytes, encoded as Base64 unicode string."""
    return encode_bytes(random_bytes(num_bytes))


def random_bytes(num_bytes):
    """Generates random bytes."""
    return os.urandom(num_bytes)


def encode_bytes(bytes):
    """Encodes bytes as Base64 unicode string."""
    return b64encode(bytes).decode('utf-8')


def decode_bytes(s):
    """Decodes bytes from Base64 encoded unicode string."""
    return b64decode(s.encode('utf-8'))
