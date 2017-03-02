from eventsourcing.domain.services.cipher import AESCipher
from eventsourcing.tests.base import AbstractTestCase
from eventsourcing.tests.example_application_tests.test_example_application_with_cassandra import \
    TestExampleApplicationWithCassandra


class CipheringTestCase(AbstractTestCase):
    def cipher(self):
        return AESCipher(aes_key='0123456789abcdef')


class TestExampleApplicationWithEncryption(CipheringTestCase, TestExampleApplicationWithCassandra):
    pass
