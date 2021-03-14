This document describes how to setup MacOS with databases needed to run the test suite:

- MySQL
- PostgreSQL
- Redis
- Cassandra
- Axon Server
- DynamoDB Local


To setup MySQL:

    $ brew install mysql
    $ brew services start mysql
    $ mysql -u root
    mysql> CREATE DATABASE eventsourcing;
    mysql> CREATE USER 'eventsourcing'@'localhost' IDENTIFIED BY 'eventsourcing';
    mysql> GRANT ALL PRIVILEGES ON eventsourcing.* TO 'eventsourcing'@'localhost';

To setup PostgreSQL:

    $ brew install postgresql
    $ brew services start postgresql


To setup Redis:

    $ brew install redis
    $ brew services start redis


To setup Cassandra:

    $ brew install cassandra
    $ brew services start cassandra

If that doesn't actually start Cassandra, then try this in a terminal:

    $ cassandra -f


To setup Axon:

    $ ./dev/download_axon_server.sh
    $ ./axonserver/axonserver.jar


To setup DynamoDB Local:

    $ ./dev/download_dynamodb_local.sh
    $ java -Djava.library.path=./dynamodb_local/DynamoDBLocal_lib -jar ./dynamodb_local/DynamoDBLocal.jar -sharedDb &


After this, the databases can be stopped with:

    $ make brew-services-stop


The databases can be started with:

    $ make brew-services-start
