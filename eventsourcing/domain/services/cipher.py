from abc import ABCMeta, abstractmethod

import six


class AbstractCipher(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def encrypt(self, plaintext):
        """Return ciphertext for given plaintext."""

    @abstractmethod
    def decrypt(self, ciphertext):
        """Return plaintext for given ciphertext."""
