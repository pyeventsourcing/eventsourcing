import os
from setuptools import find_packages, setup

try:
    from functools import singledispatch

    singledispatch_requires = []
except ImportError:
    singledispatch_requires = ['singledispatch==3.4.0.3']

from eventsourcing import __version__

# Read the docs doesn't need to build the Cassandra driver (and can't).
if 'READTHEDOCS' in os.environ:
    os.environ['CASS_DRIVER_NO_CYTHON'] = '1'

install_requires = singledispatch_requires + [
    'python-dateutil<=2.6.99999',
    'six<=1.11.99999',
    'pycryptodome<=3.4.99999',
]

sqlalchemy_requires = [
    'sqlalchemy<=1.2.99999,>=0.9',
    'sqlalchemy-utils<=0.32.99999',
]

cassandra_requires = [
    'cassandra-driver<=3.12.99999'
]

django_requires = [  # Note, Django 2 doesn't support Python 2.7
    'django>=1.11,<=2.0.99999' if str != bytes else 'django>=1.11,<=1.11.99999',
]

testing_requires = [
    'mock<=2.0.99999',
    'requests<=2.18.99999',
    'flask<=0.12.99999',
    'flask_sqlalchemy<=2.3.99',
    'uwsgi<=2.0.99999',
    'redis<=2.10.99999',
    'celery<=4.1.99999',
] + cassandra_requires + sqlalchemy_requires + django_requires

docs_requires = ['Sphinx', 'sphinx_rtd_theme', 'sphinx-autobuild'] + testing_requires


long_description = """
A library for event sourcing in Python.

`Package documentation is now available <http://eventsourcing.readthedocs.io/>`_.

`Please raise issues on GitHub <https://github.com/johnbywater/eventsourcing/issues>`_.
"""

packages = find_packages(
    exclude=[
        "docs",
        # "eventsourcing.contrib*",
        # "eventsourcing.tests*"
    ]
)

setup(
    name='eventsourcing',
    version=__version__,
    description='Event sourcing in Python',
    author='John Bywater',
    author_email='john.bywater@appropriatesoftware.net',
    url='https://github.com/johnbywater/eventsourcing',
    packages=packages,
    install_requires=install_requires,
    extras_require={
        'cassandra': cassandra_requires,
        'sqlalchemy': sqlalchemy_requires,
        'django': django_requires,
        'testing': testing_requires,
        'docs': docs_requires,
    },
    zip_safe=False,
    long_description=long_description,
    keywords=['event sourcing', 'event store', 'domain driven design', 'ddd', 'cqrs', 'cqs'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
