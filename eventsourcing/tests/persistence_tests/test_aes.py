from base64 import b64encode
from unittest.case import TestCase

from eventsourcing.cipher import AESCipher


class TestAESCipher(TestCase):
    def test_createkey(self):

        # Valid key lengths.
        key = AESCipher.create_key(16)
        AESCipher(key)

        key = AESCipher.create_key(24)
        AESCipher(key)

        key = AESCipher.create_key(32)
        AESCipher(key)

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
        with self.assertRaises(ValueError):
            AESCipher(key)

        key = create_key(20)
        with self.assertRaises(ValueError):
            AESCipher(key)

        key = create_key(28)
        with self.assertRaises(ValueError):
            AESCipher(key)

        key = create_key(36)
        with self.assertRaises(ValueError):
            AESCipher(key)

    def test_encrypt_and_decrypt(self):
        key = AESCipher.create_key(16)

        # Check plain text can be encrypted and recovered.
        plain_text = b"some text"
        cipher = AESCipher(key)
        cipher_text = cipher.encrypt(plain_text)
        cipher = AESCipher(key)
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
        cipher = AESCipher(key)
        with self.assertRaises(ValueError):
            cipher.decrypt(cipher_text)
