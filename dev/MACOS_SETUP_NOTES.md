This section describes how to setup PostgreSQL on MacOS so developers can run the test suite:

- install postgresl with homebrew:

$ brew install postgresql

- edit pg_hba.conf so that passwords are required when connecting with TCP/IP:

$ vim /opt/homebrew/var/postgresql@14/pg_hba.conf

# TYPE  DATABASE        USER            ADDRESS                 METHOD
# "local" is for Unix domain socket connections only
local   all             all                                     trust
# IPv4 local connections:
host    all             all             127.0.0.1/32            md5
# IPv6 local connections:
host    all             all             ::1/128                 md5

- start PostgreSQL

$ brew services start postgresql

- create roles for 'postgres' and 'eventsourcing', and create databases 'eventsourcing' and 'eventsourcing_nopublic'
$ psql postgres
postgres=> CREATE ROLE postgres LOGIN SUPERUSER PASSWORD 'postgres';
postgres=> CREATE USER eventsourcing WITH PASSWORD 'eventsourcing';
postgres=> CREATE DATABASE eventsourcing;
postgres=> ALTER DATABASE eventsourcing OWNER TO eventsourcing;
postgres=> CREATE DATABASE eventsourcing_nopublic;
postgres=> ALTER DATABASE eventsourcing_nopublic OWNER TO eventsourcing;

- create 'myschema' schema in eventsourcing database
$ psql eventsourcing
eventsourcing=> CREATE SCHEMA myschema AUTHORIZATION eventsourcing;

- create 'myschema' schema and drop 'public' schema in eventsourcing_nopublic database
$ psql eventsourcing_nopublic
eventsourcing_nopublic=> CREATE SCHEMA myschema AUTHORIZATION eventsourcing;
eventsourcing_nopublic=> DROP SCHEMA public;


To build PDF docs (make docs-pdf), download and install MacTeX from https://www.tug.org/mactex/mactex-download.html
and then make sure latexmk is on your PATH (export PATH="$PATH:/Library/TeX/texbin").

To use psycopg without psycopg-c or psycopg-binary (e.g. when testing beta versions of new Python releases
before psycopg-binary has been released), install libpq with homebrew:

$ brew install libpq
