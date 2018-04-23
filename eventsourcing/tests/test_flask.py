import os
import platform
import sys
import unittest
from os.path import abspath, dirname, join
from subprocess import Popen
from tempfile import NamedTemporaryFile
from time import sleep
from unittest.case import skipIf

import requests
from requests.exceptions import ConnectionError
from requests.models import Response

import eventsourcing.example.interface
from eventsourcing.domain.model.events import assert_event_handlers_empty
from eventsourcing.example.application import close_example_application
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
from eventsourcing.tests.base import notquick

path_to_virtualenv = None
if hasattr(sys, 'real_prefix'):
    path_to_virtualenv = sys.prefix

path_to_eventsourcing = dirname(dirname(abspath(eventsourcing.__file__)))
path_to_interface_module = dirname(abspath(eventsourcing.example.interface.__file__))
path_to_flaskapp = join(path_to_interface_module, 'flaskapp.py')
path_to_flaskwsgi = join(dirname(path_to_flaskapp), 'flaskwsgi.py')


@notquick
class TestFlaskApp(unittest.TestCase):
    port = 5001

    def setUp(self):
        assert_event_handlers_empty()
        super(TestFlaskApp, self).setUp()
        self.app = self.start_app()

    def start_app(self):
        cmd = [sys.executable, path_to_flaskapp]
        return Popen(cmd)

    def tearDown(self):
        self.app.terminate()
        sleep(1)
        self.app.kill()
        sleep(1)
        self.app.wait()
        super(TestFlaskApp, self).tearDown()
        assert_event_handlers_empty()

    def test(self):
        patience = 100
        while True:
            try:
                response = requests.get('http://localhost:{}'.format(self.port))
                break
            except ConnectionError:
                patience -= 1
                if not patience:
                    self.fail("Couldn't get response from app, (Python executable {})".format(sys.executable))
                else:
                    sleep(0.1)

        self.assertIsInstance(response, Response)
        self.assertIn('Hello There!', response.text)


@notquick
@skipIf(platform.python_implementation() == 'PyPy', 'uWSGI needs special plugin to run with PyPy')
class TestFlaskWsgi(TestFlaskApp):
    port = 9001

    def start_app(self):
        # Make up a DB URI using a named temporary file.
        self.tempfile = NamedTemporaryFile()
        uri = 'sqlite:///{}'.format(self.tempfile.name)

        from eventsourcing.example.interface.flaskapp import IntegerSequencedItem
        # Close application, importing the module constructed
        # the application, which will leave event handlers subscribed.
        close_example_application()

        # Setup tables.
        datastore = SQLAlchemyDatastore(
            settings=SQLAlchemySettings(uri=uri),
            tables=(IntegerSequencedItem,),
        )
        datastore.setup_connection()
        datastore.setup_tables()
        datastore.close_connection()

        # Run uwsgi.
        if path_to_virtualenv:
            path_to_uwsgi = join(path_to_virtualenv, 'bin', 'uwsgi')
            assert os.path.exists(path_to_uwsgi), path_to_uwsgi
        else:
            # In a container, without a virtualenv?
            path_to_uwsgi = '/usr/local/bin/uwsgi'
            # Todo: Maybe use shutil.which, after dropping support for Python 2.7.

        cmd = [path_to_uwsgi]
        if path_to_virtualenv is not None:
            cmd += ['-H', path_to_virtualenv]
        cmd += ['--master']
        cmd += ['--processes', '4']
        cmd += ['--threads', '2']
        cmd += ['--wsgi-file', path_to_flaskwsgi]
        cmd += ['--http', ':{}'.format(self.port)]
        pythonpath = ':'.join(os.getenv('PYTHONPATH', '').split(':') + [path_to_eventsourcing])
        return Popen(cmd, env={
            'PYTHONPATH': pythonpath,
            'DB_URI': uri
        })
