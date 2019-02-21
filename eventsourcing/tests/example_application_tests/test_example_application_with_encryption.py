from eventsourcing.utils.cipher.aes import AESCipher
from eventsourcing.tests.example_application_tests import base
from eventsourcing.tests.example_application_tests.test_example_application_with_cassandra import \
    TestExampleApplicationWithCassandra
from eventsourcing.tests.example_application_tests.test_example_application_with_sqlalchemy import \
    TestExampleApplicationWithSQLAlchemy


class WithEncryption(base.WithExampleApplication):
    def construct_cipher(self):
        return AESCipher(cipher_key=b'0123456789abcdef')


class TestEncryptedApplicationWithCassandra(WithEncryption, TestExampleApplicationWithCassandra):
    pass


class TestEncryptedApplicationWithSQLAlchemy(WithEncryption, TestExampleApplicationWithSQLAlchemy):
    pass
