from base64 import b64encode, b64decode

import os


def generate_cipher_key(num_bytes):
    """Generates random bytes, encoded as Base64 unicode string."""
    return b64encode(os.urandom(num_bytes)).decode('utf-8')


def decode_cipher_key(cipher_key):
    """Returns bytes, decoded from Base64 encoded unicode string."""
    return b64decode(cipher_key.encode('utf-8'))
