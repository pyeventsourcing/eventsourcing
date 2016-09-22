import base64

import zlib
from Crypto import Random
from Crypto.Cipher import AES

from eventsourcing.application.example.with_cassandra import ExampleApplicationWithCassandra
from eventsourcing.tests.test_application_with_cassandra import TestApplicationWithCassandra


class TestApplicationWithEncryption(TestApplicationWithCassandra):

    def create_app(self):
        cipher = AESStoredEventCipher(aes_key='0123456789abcdef')
        return ExampleApplicationWithCassandra(cipher=cipher)


class AESStoredEventCipher(object):

    BLOCK_SIZE = 16

    def __init__(self, aes_key):
        self.aes_key = aes_key

        # Pick AES mode.
        self.aes_mode = AES.MODE_CBC

        # Fix the block size.
        self.bs = AES.block_size

    def encrypt(self, plaintext):
        # Create a unique initialisation vector each time something is encrypted.
        iv = Random.new().read(self.bs)

        # Create an AES cipher.
        cipher = AES.new(self.aes_key, self.aes_mode, iv)

        # Construct the ciphertext string.
        ciphertext = base64.b64encode(
            iv + cipher.encrypt(
                self._pad(
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
        # Recover the initialisation vector.
        ciphertext_bytes_base64 = ciphertext.encode('utf8')
        ciphertext_bytes = base64.b64decode(ciphertext_bytes_base64)
        iv = ciphertext_bytes[:self.bs]

        # Create the AES cipher.
        cipher = AES.new(self.aes_key, self.aes_mode, iv)

        # Construct the plaintext string.
        plaintext = zlib.decompress(
            base64.b64decode(
                self._unpad(
                    cipher.decrypt(
                        ciphertext_bytes[self.bs:]
                    )
                )
            )
        ).decode('utf8')

        return plaintext

    def _pad(self, s):
        padding_size = self.bs - len(s) % self.bs
        return s + padding_size * chr(padding_size).encode('utf8')

    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s)-1:])]
