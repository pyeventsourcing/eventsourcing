============================
Application-level encryption
============================

To enable encryption, pass in a cipher strategy object when constructing
the sequenced item mapper, and set ``always_encrypt`` to a True value.

Cipher
------

This example uses the AES cipher strategy provided by this library. Alternatively,
you can craft your own cipher strategy object.

With encryption enabled, event attribute values are encrypted inside the application
before they are mapped to the database. The values are decrypted before domain events
are replayed.


.. code:: python

    from eventsourcing.domain.services.aes_cipher import AESCipher

    # Construct the cipher strategy.
    aes_key = '0123456789abcdef'
    cipher = AESCipher(aes_key)


Application and infrastructure
------------------------------

Setup infrastructure using library classes.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings, SQLAlchemyDatastore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SqlIntegerSequencedItem

    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
        tables=(SqlIntegerSequencedItem,),
    )

    datastore.setup_connection()
    datastore.setup_tables()


Define a factory that uses library classes to construct an application object.

.. code:: python

    from eventsourcing.example.application import ExampleApplication
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.infrastructure.sequenceditem import SequencedItem

    def construct_example_application(datastore, always_encrypt=False, cipher=None):
        active_record_strategy = SQLAlchemyActiveRecordStrategy(
            active_record_class=SqlIntegerSequencedItem,
            sequenced_item_class=SequencedItem,
            session=datastore.db_session
        )
        app = ExampleApplication(
            integer_sequenced_active_record_strategy=active_record_strategy,
            always_encrypt=always_encrypt,
            cipher=cipher,
        )
        return app


Run the code
------------

.. code:: python

    # Create a new example entity using an encrypted application.
    encrypted_app = construct_example_application(datastore, always_encrypt=True, cipher=cipher)

    with encrypted_app as app:
        secret_entity = app.create_new_example(foo='secret info')

        # With encryption enabled, application state is not visible in the database.
        event_store = app.integer_sequenced_event_store
        item2 = event_store.active_record_strategy.get_item(secret_entity.id, 0)
        assert 'secret info' not in item2.data

        # Events are decrypted inside the application.
        retrieved_entity = app.example_repository[secret_entity.id]
        assert 'secret info' in retrieved_entity.foo

    # Create a new example entity using an unencrypted application.
    unencrypted_app = construct_example_application(datastore)
    with unencrypted_app as app:
        entity = app.create_new_example(foo='bar')

        # Without encryption, application state is visible in the database.
        event_store = app.integer_sequenced_event_store
        item1 = event_store.active_record_strategy.get_item(entity.id, 0)
        assert 'bar' in item1.data
