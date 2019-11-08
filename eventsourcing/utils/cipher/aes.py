import base64
import zlib

from Crypto.Cipher import AES

from eventsourcing.exceptions import DataIntegrityError
from eventsourcing.utils.random import random_bytes


STORE_BYTES = True


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
        plainbytes = plaintext.encode("utf8")

        # Compress plaintext bytes.
        compressed = zlib.compress(plainbytes)

        # Construct AES-GCM cipher, with 96-bit nonce.
        cipher = AES.new(self.cipher_key, AES.MODE_GCM, nonce=random_bytes(12))

        # Encrypt and digest.
        encrypted, tag = cipher.encrypt_and_digest(compressed)

        # Combine with nonce.
        cipherbytes = cipher.nonce + tag + encrypted

        if STORE_BYTES:
            # Just return the bytes.
            return cipherbytes
        else:
            # Encode as Base64.
            base64bytes = base64.b64encode(cipherbytes)

            # Bytes to string.
            ciphertext = base64bytes.decode("utf8")

            # Return ciphertext.
            return ciphertext

    def decrypt(self, ciphertext):
        """Return plaintext for given ciphertext."""

        if STORE_BYTES:
            # Just assume its bytes.
            cipherbytes = ciphertext
        else:
            # String to bytes.
            base64bytes = ciphertext.encode("utf8")

            # Decode from Base64.
            try:
                cipherbytes = base64.b64decode(base64bytes)
            except (base64.binascii.Error, TypeError) as e:
                # base64.binascii.Error for Python 3.
                # TypeError for Python 2.
                raise DataIntegrityError("Cipher text is damaged: {}".format(e))

        # Split out the nonce, tag, and encrypted data.
        nonce = cipherbytes[:12]
        if len(nonce) != 12:
            raise DataIntegrityError("Cipher text is damaged: invalid nonce length")

        tag = cipherbytes[12:28]
        if len(tag) != 16:
            raise DataIntegrityError("Cipher text is damaged: invalid tag length")

        encrypted = cipherbytes[28:]

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
        plaintext = plainbytes.decode("utf8")

        # Return plaintext.
        return plaintext
