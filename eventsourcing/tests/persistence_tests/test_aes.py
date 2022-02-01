from base64 import b64encode
from unittest.case import TestCase

from eventsourcing.cipher import AESCipher
from eventsourcing.utils import Environment


class TestAESCipher(TestCase):
    def test_createkey(self):
        environment = Environment()

        # Valid key lengths.
        key = AESCipher.create_key(16)
        environment["CIPHER_KEY"] = key
        AESCipher(environment)

        key = AESCipher.create_key(24)
        environment["CIPHER_KEY"] = key
        AESCipher(environment)

        key = AESCipher.create_key(32)
        environment["CIPHER_KEY"] = key
        AESCipher(environment)

        # Non-valid key lengths (on generate key).
        with self.assertRaises(ValueError):
            AESCipher.create_key(12)

        with self.assertRaises(ValueError):
            AESCipher.create_key(20)

        with self.assertRaises(ValueError):
            AESCipher.create_key(28)

        with self.assertRaises(ValueError):
            AESCipher.create_key(36)

        # Non-valid key lengths (on construction).
        def create_key(num_bytes):
            return b64encode(AESCipher.random_bytes(num_bytes)).decode("utf8")

        key = create_key(12)
        environment["CIPHER_KEY"] = key
        with self.assertRaises(ValueError):
            AESCipher(environment)

        key = create_key(20)
        environment["CIPHER_KEY"] = key
        with self.assertRaises(ValueError):
            AESCipher(environment)

        key = create_key(28)
        environment["CIPHER_KEY"] = key
        with self.assertRaises(ValueError):
            AESCipher(environment)

        key = create_key(36)
        environment["CIPHER_KEY"] = key
        with self.assertRaises(ValueError):
            AESCipher(environment)

    def test_encrypt_and_decrypt(self):
        environment = Environment()

        key = AESCipher.create_key(16)
        environment["CIPHER_KEY"] = key

        # Check plain text can be encrypted and recovered.
        plain_text = b"some text"
        cipher = AESCipher(environment)
        cipher_text = cipher.encrypt(plain_text)
        cipher = AESCipher(environment)
        recovered_text = cipher.decrypt(cipher_text)
        self.assertEqual(recovered_text, plain_text)

        # Check raises on invalid nonce.
        with self.assertRaises(ValueError):
            cipher.decrypt(cipher_text[:10])

        # Check raises on invalid tag.
        with self.assertRaises(ValueError):
            cipher.decrypt(cipher_text[:20])

        # Check raises on invalid data.
        with self.assertRaises(ValueError):
            cipher.decrypt(cipher_text[:30])

        # Check raises on invalid key.
        key = AESCipher.create_key(16)
        environment["CIPHER_KEY"] = key
        cipher = AESCipher(environment)
        with self.assertRaises(ValueError):
            cipher.decrypt(cipher_text)
