from Crypto.Cipher import AES

from eventsourcing.exceptions import DataIntegrityError
from eventsourcing.utils.random import random_bytes


class AESCipher(object):
    """
    Cipher strategy that uses Crypto library AES cipher in GCM mode.
    """

    def __init__(self, cipher_key: bytes):
        """
        Initialises AES cipher strategy with ``cipher_key``.

        :param cipher_key: 16, 24, or 32 random bytes
        """
        assert len(cipher_key) in [16, 24, 32]
        self.cipher_key = cipher_key

    def encrypt(self, plaintext: bytes) -> bytes:
        """Return ciphertext for given plaintext."""

        # Construct AES-GCM cipher, with 96-bit nonce.
        cipher = AES.new(self.cipher_key, AES.MODE_GCM, nonce=random_bytes(12))

        # Encrypt and digest.
        encrypted, tag = cipher.encrypt_and_digest(plaintext)  # type: ignore

        # Combine with nonce.
        ciphertext = cipher.nonce + tag + encrypted  # type: ignore

        # Return ciphertext.
        return ciphertext

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Return plaintext for given ciphertext."""

        # Split out the nonce, tag, and encrypted data.
        nonce = ciphertext[:12]
        if len(nonce) != 12:
            raise DataIntegrityError("Cipher text is damaged: invalid nonce length")

        tag = ciphertext[12:28]
        if len(tag) != 16:
            raise DataIntegrityError("Cipher text is damaged: invalid tag length")

        encrypted = ciphertext[28:]

        # Construct AES cipher, with old nonce.
        cipher = AES.new(self.cipher_key, AES.MODE_GCM, nonce)

        # Decrypt and verify.
        try:
            plaintext = cipher.decrypt_and_verify(encrypted, tag)  # type: ignore
        except ValueError as e:
            raise DataIntegrityError("Cipher text is damaged: {}".format(e))
        return plaintext
