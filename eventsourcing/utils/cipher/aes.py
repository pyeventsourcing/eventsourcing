import base64
import zlib

from Crypto import Random
from Crypto.Cipher import AES

from eventsourcing.utils.cipher.base import AbstractCipher

DEFAULT_AES_MODE = 'GCM'


class AESCipher(AbstractCipher):
    """
    Cipher strategy that uses Crypto library AES cipher in GCM mode.
    """

    # Todo: Follow docs http://pycryptodome.readthedocs.io/en/latest/src/examples.html#encrypt-data-with-aes

    SUPPORTED_MODES = ['CBC', 'EAX', 'GCM', 'CCM']
    PADDED_MODES = ['CBC']

    def __init__(self, aes_key, mode_name=None):
        self.aes_key = aes_key
        self.mode_name = mode_name or DEFAULT_AES_MODE

        # Check mode name is supported.
        assert self.mode_name in self.SUPPORTED_MODES, (
            "Mode '{}' not in supported list: {}".format(
                self.mode_name, self.SUPPORTED_MODES
            )
        )

        # Pick AES mode (an integer).
        self.mode = getattr(AES, 'MODE_{}'.format(self.mode_name))

        # Fix the block size.
        self.bs = AES.block_size

    def encrypt(self, plaintext):
        """Return ciphertext for given plaintext."""

        # Create a unique initialisation vector each time something is encrypted.
        iv = Random.new().read(self.bs)

        # Create an AES cipher.
        cipher = AES.new(self.aes_key, self.mode, iv)

        # Construct the ciphertext string.
        ciphertext = base64.b64encode(
            iv + cipher.encrypt(
                self.pad(
                    base64.b64encode(
                        zlib.compress(
                            plaintext.encode('utf8')
                        )
                    )
                )
            )
        ).decode('utf8')

        return ciphertext

    def decrypt(self, ciphertext):
        """Return plaintext for given ciphertext."""

        # Recover the initialisation vector.
        ciphertext_bytes_base64 = ciphertext.encode('utf8')
        ciphertext_bytes = base64.b64decode(ciphertext_bytes_base64)
        iv = ciphertext_bytes[:self.bs]

        # Create the AES cipher.
        cipher = AES.new(self.aes_key, self.mode, iv)

        # Construct the plaintext string.
        plaintext = zlib.decompress(
            base64.b64decode(
                self.unpad(
                    cipher.decrypt(
                        ciphertext_bytes[self.bs:]
                    )
                )
            )
        ).decode('utf8')

        return plaintext

    def pad(self, s):
        if self.mode_name in self.PADDED_MODES:
            padding_size = self.bs - len(s) % self.bs
            return s + padding_size * chr(padding_size).encode('utf8')
        else:
            return s

    def unpad(self, s):
        if self.mode_name in self.PADDED_MODES:
            return s[:-ord(s[len(s) - 1:])]
        else:
            return s
