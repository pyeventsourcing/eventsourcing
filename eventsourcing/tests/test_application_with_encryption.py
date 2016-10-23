from eventsourcing.application.example.with_cassandra import ExampleApplicationWithCassandra
from eventsourcing.domain.services.cipher import AESCipher
from eventsourcing.tests.test_application_with_cassandra import TestApplicationWithCassandra


class TestApplicationWithEncryption(TestApplicationWithCassandra):

    def create_app(self):
        cipher = AESCipher(aes_key='0123456789abcdef')
        return ExampleApplicationWithCassandra(cipher=cipher, always_encrypt_stored_events=True)
