from eventsourcing.domain.services.cipher import AESCipher
from eventsourcing.tests.example_application_tests.test_example_application_with_cassandra import \
    TestExampleApplicationWithCassandra, create_example_application_with_cassandra


class TestExampleApplicationWithEncryption(TestExampleApplicationWithCassandra):
    def create_app(self):
        cipher = AESCipher(aes_key='0123456789abcdef')
        return create_example_application_with_cassandra(cipher=cipher)
