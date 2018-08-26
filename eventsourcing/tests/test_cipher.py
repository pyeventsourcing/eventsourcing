from unittest import TestCase

from eventsourcing.exceptions import DataIntegrityError


class TestAESCipher(TestCase):

    def test_encrypt_mode_gcm(self):
        from eventsourcing.utils.cipher.aes import AESCipher
        from eventsourcing.utils.random import encode_random_bytes, decode_bytes

        # Unicode string representing 256 random bits encoded with Base64.
        cipher_key = encode_random_bytes(num_bytes=32)

        # Construct AES cipher.
        cipher = AESCipher(cipher_key=decode_bytes(cipher_key))

        # Encrypt some plaintext.
        ciphertext = cipher.encrypt('plaintext')
        self.assertNotEqual(ciphertext, 'plaintext')

        # Decrypt some ciphertext.
        plaintext = cipher.decrypt(ciphertext)
        self.assertEqual(plaintext, 'plaintext')

        # Check DataIntegrityError is raised (broken Base64 padding).
        with self.assertRaises(DataIntegrityError):
            damaged = ciphertext[:-1]
            cipher.decrypt(damaged)

        # Check DataIntegrityError is raised (MAC check fails).
        with self.assertRaises(DataIntegrityError):
            damaged = 'a' + ciphertext[:-1]
            cipher.decrypt(damaged)

        # Check DataIntegrityError is raised (nonce too short).
        with self.assertRaises(DataIntegrityError):
            damaged = ciphertext[:0]
            cipher.decrypt(damaged)

        # Check DataIntegrityError is raised (tag too short).
        with self.assertRaises(DataIntegrityError):
            damaged = ciphertext[:20]
            cipher.decrypt(damaged)
