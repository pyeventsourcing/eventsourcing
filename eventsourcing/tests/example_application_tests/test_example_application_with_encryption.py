from eventsourcing.domain.services.cipher import AESCipher
from eventsourcing.tests.example_application_tests.base import ExampleApplicationTestCase
from eventsourcing.tests.example_application_tests.test_new_example_application_with_cassandra import \
    TestExampleApplicationWithCassandra


class CipheringTestCase(ExampleApplicationTestCase):

    def construct_cipher(self):
        return AESCipher(aes_key='0123456789abcdef')


class TestExampleApplicationWithEncryption(CipheringTestCase, TestExampleApplicationWithCassandra):
    pass
