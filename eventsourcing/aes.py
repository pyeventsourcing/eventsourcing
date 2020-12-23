import os

from Crypto.Cipher import AES
from Crypto.Cipher._mode_gcm import GcmMode


def random_bytes(num_bytes: int) -> bytes:
    return os.urandom(num_bytes)


class AESCipher(object):
    """
    Cipher strategy that uses Crypto
    library AES cipher in GCM mode.
    """

    def __init__(self, cipher_key: bytes):
        """
        Initialises AES cipher with ``cipher_key``.

        :param cipher_key: 16, 24, or 32 random bytes
        """
        assert len(cipher_key) in [16, 24, 32]
        self.cipher_key = cipher_key

    def encrypt(self, plaintext: bytes) -> bytes:
        """Return ciphertext for given plaintext."""

        # Construct AES-GCM cipher, with 96-bit nonce.
        nonce = random_bytes(12)
        cipher = self.construct_cipher(nonce)

        # Encrypt and digest.
        result = cipher.encrypt_and_digest(plaintext)
        encrypted = result[0]
        tag = result[1]

        # Combine with nonce.
        ciphertext = nonce + tag + encrypted

        # Return ciphertext.
        return ciphertext

    def construct_cipher(self, nonce: bytes) -> GcmMode:
        cipher = AES.new(
            self.cipher_key,
            AES.MODE_GCM,
            nonce,
        )
        assert isinstance(cipher, GcmMode)
        return cipher

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Return plaintext for given ciphertext."""

        # Split out the nonce, tag, and encrypted data.
        nonce = ciphertext[:12]
        if len(nonce) != 12:
            raise Exception(
                "Damaged cipher text: invalid nonce length"
            )

        tag = ciphertext[12:28]
        if len(tag) != 16:
            raise Exception(
                "Damaged cipher text: invalid tag length"
            )
        encrypted = ciphertext[28:]

        # Construct AES cipher, with old nonce.
        cipher = self.construct_cipher(nonce)

        # Decrypt and verify.
        try:
            plaintext = cipher.decrypt_and_verify(
                encrypted, tag
            )
        except ValueError as e:
            raise ValueError(
                "Cipher text is damaged: {}".format(e)
            )
        return plaintext
