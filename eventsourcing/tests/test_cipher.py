from unittest import TestCase

from Crypto.Cipher import AES


class TestAESCipher(TestCase):
    def test_encrypt_mode_eax(self):
        self.check_cipher('EAX', AES.MODE_EAX)

    def test_encrypt_mode_cbc(self):
        self.check_cipher('CBC', AES.MODE_CBC)

    def test_encrypt_mode_gcm(self):
        self.check_cipher('GCM', AES.MODE_GCM)

    def check_cipher(self, mode_name, expect_mode):
        from eventsourcing.utils.cipher.aes import AESCipher
        from eventsourcing.utils.random import encode_random_bytes, decode_random_bytes

        # Unicode string representing 256 random bits encoded with Base64.
        cipher_key = encode_random_bytes(num_bytes=32)

        # Construct AES-256 cipher.
        cipher = AESCipher(
            aes_key=decode_random_bytes(cipher_key),
            mode_name=mode_name
        )

        # Check mode.
        self.assertEqual(cipher.mode, expect_mode)

        # Encrypt some plaintext.
        ciphertext = cipher.encrypt('plaintext')
        self.assertNotEqual(ciphertext, 'plaintext')

        # Decrypt some ciphertext.
        plaintext = cipher.decrypt(ciphertext)
        self.assertEqual(plaintext, 'plaintext')
