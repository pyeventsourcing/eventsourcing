from setuptools import find_packages, setup

try:
    from functools import singledispatch

    singledispatch_requires = []
except ImportError:
    singledispatch_requires = ['singledispatch==3.4.0.3']

from eventsourcing import __version__

install_requires = singledispatch_requires + [
    'python-dateutil<=2.6.99999',
    'six<=1.10.99999',
]

sqlalchemy_requires = [
    'sqlalchemy<=1.1.99999',
    'sqlalchemy-utils<=0.32.99999',
]

cassandra_requires = [
    'cassandra-driver<=3.9.99999'
]

crypto_requires = ['PyCrypto<=2.6.99999']

testing_requires = [
    'mock<=2.0.99999',
    'requests<=2.13.99999',
    'flask<=0.12.99999',
    'flask_sqlalchemy<=2.2.99',
    'uwsgi<=2.0.99999',
    'redis<=2.10.99999',
    'celery<=4.0.99999',
]

long_description = """
This package provides generic support for event sourcing in Python.

An extensive
`README file is available on GitHub <https://github.com/johnbywater/eventsourcing/blob/master/README.md>`_.
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
        'crypto': crypto_requires,
        'sqlalchemy': sqlalchemy_requires,
        'testing': cassandra_requires + crypto_requires + sqlalchemy_requires + testing_requires,
    },
    zip_safe=False,
    long_description=long_description,
    keywords=['event sourcing', 'event store', 'domain driven design', 'ddd', 'cqrs', 'cqs'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
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
