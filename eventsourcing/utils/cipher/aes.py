import base64
import zlib

from Crypto.Cipher import AES

from eventsourcing.exceptions import DataIntegrityError
from eventsourcing.utils.random import random_bytes


class AESCipher(object):
    """
    Cipher strategy that uses Crypto library AES cipher in GCM mode.
    """

    def __init__(self, cipher_key):
        """
        Initialises AES cipher strategy with ``cipher_key``.

        :param cipher_key: 16, 24, or 32 random bytes
        """
        assert len(cipher_key) in [16, 24, 32]
        self.cipher_key = cipher_key

    def encrypt(self, plaintext):
        """Return ciphertext for given plaintext."""

        # String to bytes.
        plainbytes = plaintext.encode('utf8')

        # Compress plaintext bytes.
        compressed = zlib.compress(plainbytes)

        # Construct AES-GCM cipher, with 96-bit nonce.
        cipher = AES.new(self.cipher_key, AES.MODE_GCM, nonce=random_bytes(12))

        # Encrypt and digest.
        encrypted, tag = cipher.encrypt_and_digest(compressed)

        # Combine with nonce.
        combined = cipher.nonce + tag + encrypted

        # Encode as Base64.
        cipherbytes = base64.b64encode(combined)

        # Bytes to string.
        ciphertext = cipherbytes.decode('utf8')

        # Return ciphertext.
        return ciphertext

    def decrypt(self, ciphertext):
        """Return plaintext for given ciphertext."""

        # String to bytes.
        cipherbytes = ciphertext.encode('utf8')

        # Decode from Base64.
        try:
            combined = base64.b64decode(cipherbytes)
        except (base64.binascii.Error, TypeError) as e:
            # base64.binascii.Error for Python 3.
            # TypeError for Python 2.
            raise DataIntegrityError("Cipher text is damaged: {}".format(e))

        # Split out the nonce, tag, and encrypted data.
        nonce = combined[:12]
        if len(nonce) != 12:
            raise DataIntegrityError("Cipher text is damaged: invalid nonce length")

        tag = combined[12:28]
        if len(tag) != 16:
            raise DataIntegrityError("Cipher text is damaged: invalid tag length")

        encrypted = combined[28:]

        # Construct AES cipher, with old nonce.
        cipher = AES.new(self.cipher_key, AES.MODE_GCM, nonce)

        # Decrypt and verify.
        try:
            compressed = cipher.decrypt_and_verify(encrypted, tag)
        except ValueError as e:
            raise DataIntegrityError("Cipher text is damaged: {}".format(e))

        # Decompress plaintext bytes.
        plainbytes = zlib.decompress(compressed)

        # Bytes to string.
        plaintext = plainbytes.decode('utf8')

        # Return plaintext.
        return plaintext
