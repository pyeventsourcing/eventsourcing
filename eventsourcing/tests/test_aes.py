from unittest.case import TestCase

from eventsourcing.cipher import AESCipher


class TestAESCipher(TestCase):
    def test_create_key(self):

        # Valid key lengths.
        key = AESCipher.create_key(16)
        AESCipher(key)

        key = AESCipher.create_key(24)
        AESCipher(key)

        key = AESCipher.create_key(32)
        AESCipher(key)

        # Non-valid key lengths.
        key = AESCipher.create_key(12)
        with self.assertRaises(AssertionError):
            AESCipher(key)

        key = AESCipher.create_key(20)
        with self.assertRaises(AssertionError):
            AESCipher(key)

        key = AESCipher.create_key(28)
        with self.assertRaises(AssertionError):
            AESCipher(key)

        key = AESCipher.create_key(36)
        with self.assertRaises(AssertionError):
            AESCipher(key)


    def test_encrypt_and_decrypt(self):
        key = AESCipher.create_key(16)

        # Check plain text can be encrypted and recovered.
        plain_text = b'some text'
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

        # Check raises on invalid tag.
        with self.assertRaises(ValueError):
            cipher.decrypt(cipher_text[:30])
