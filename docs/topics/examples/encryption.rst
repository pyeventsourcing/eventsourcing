============================
Application-level encryption
============================


Install the library with the 'crypto' option.

::

    $ pip install eventsourcing[crypto]


To enable encryption, pass in a cipher strategy object when constructing
the sequenced item mapper, and set ``always_encrypt`` to a True value.

Cipher strategy
---------------

Let's firstly construct a cipher strategy object. This example uses the
library AES cipher strategy :class:`~eventsourcing.infrastructure.cipher.aes.AESCipher`.

The library AES cipher strategy uses the AES cipher from the `Python Cryptography
Toolkit <https://pypi.python.org/pypi/pycrypto>`__, by default in CBC mode with
128 bit blocksize and a 16 byte encryption key. It generates a unique 16 byte
initialization vector for each encryption. In this cipher strategy, serialized
event data is compressed before it is encrypted, which can mean application
performance is improved when encryption is enabled.

With encryption enabled, event attribute values are encrypted inside the application
before they are mapped to the database. The values are decrypted before domain events
are replayed.

.. code:: python

    from eventsourcing.infrastructure.cipher.aes import AESCipher

    # Construct the cipher strategy.
    aes_key = b'0123456789abcdef'
    cipher = AESCipher(aes_key)


Application and infrastructure
------------------------------

Set up infrastructure using library classes.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings, SQLAlchemyDatastore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import IntegerSequencedItemRecord

    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
        tables=(IntegerSequencedItemRecord,),
    )

    datastore.setup_connection()
    datastore.setup_tables()


Define a factory that uses library classes to construct an application object.

.. code:: python

    from eventsourcing.example.application import ExampleApplication
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.infrastructure.sequenceditem import SequencedItem

    def construct_example_application(session, always_encrypt=False, cipher=None):
        active_record_strategy = SQLAlchemyActiveRecordStrategy(
            active_record_class=IntegerSequencedItemRecord,
            session=session
        )
        app = ExampleApplication(
            entity_active_record_strategy=active_record_strategy,
            always_encrypt=always_encrypt,
            cipher=cipher,
        )
        return app


Run the code
------------

Now construct an encrypted application with the cipher. Create an
"example" with some "secret information". Check the information
is not visible in the database, as it is when the application is not
encrypted.

.. code:: python

    # Create a new example entity using an encrypted application.
    encrypted_app = construct_example_application(datastore.session, always_encrypt=True, cipher=cipher)

    with encrypted_app as app:
        secret_entity = app.create_new_example(foo='secret info')

        # With encryption enabled, application state is not visible in the database.
        event_store = app.entity_event_store
        item2 = event_store.active_record_strategy.get_item(secret_entity.id, eq=0)
        assert 'secret info' not in item2.data

        # Events are decrypted inside the application.
        retrieved_entity = app.example_repository[secret_entity.id]
        assert 'secret info' in retrieved_entity.foo

    # Create a new example entity using an unencrypted application object.
    unencrypted_app = construct_example_application(datastore.session)
    with unencrypted_app as app:
        entity = app.create_new_example(foo='bar')

        # Without encryption, application state is visible in the database.
        event_store = app.entity_event_store
        item1 = event_store.active_record_strategy.get_item(entity.id, 0)
        assert 'bar' in item1.data
