import base64
import zlib

from Crypto import Random
from Crypto.Cipher import AES

from eventsourcing.utils.cipher.base import AbstractCipher


class AESCipher(AbstractCipher):
    """
    Cipher strategy that uses the AES cipher from the Crypto library.

    Defaults to GCM mode. Unlike CBC, GCM doesn't need padding so avoids
    potential padding oracle attacks. GCM will be faster than EAX on
    x86 architectures, especially those with AES opcodes.
    """
    SUPPORTED_MODES = ['CBC', 'EAX', 'GCM']
    PADDED_MODES = ['CBC']

    def __init__(self, aes_key, mode_name='GCM'):
        self.aes_key = aes_key
        self.mode_name = mode_name

        # Check mode name is supported.
        assert mode_name in self.SUPPORTED_MODES, (
            "Mode '{}' not in supported list: {}".format(
                mode_name, self.SUPPORTED_MODES
            )
        )

        # Pick AES mode (an integer).
        self.mode = getattr(AES, 'MODE_{}'.format(mode_name))

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
