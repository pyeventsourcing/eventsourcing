import base64
import zlib

from Crypto.Cipher import AES

from eventsourcing.exceptions import DataIntegrityError
from eventsourcing.utils.cipher.base import AbstractCipher


class AESCipher(AbstractCipher):
    """
    Cipher strategy that uses Crypto library AES cipher in GCM mode.
    """
    def __init__(self, aes_key):
        self.aes_key = aes_key

    def encrypt(self, plaintext):
        """Return ciphertext for given plaintext."""

        # String to bytes.
        plainbytes = plaintext.encode('utf8')

        # Compress plaintext bytes.
        compressed = zlib.compress(plainbytes)

        # Construct AES cipher, with new nonce.
        cipher = AES.new(self.aes_key, AES.MODE_GCM)

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
        nonce = combined[:16]
        tag = combined[16:32]
        encrypted = combined[32:]

        # Construct AES cipher, with old nonce.
        cipher = AES.new(self.aes_key, AES.MODE_GCM, nonce)

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
