import os
import platform

from setuptools import find_packages, setup

from eventsourcing import __version__

is_pypy = platform.python_implementation() == "PyPy"

# Read the docs doesn't need to build the Cassandra driver (and can't).
if "READTHEDOCS" in os.environ:
    os.environ["CASS_DRIVER_NO_CYTHON"] = "1"

install_requires = [
    "python-dateutil<=2.8.99999",
    "pycryptodome<=3.9.99999",
    "requests<=2.25.99999",
    "readerwriterlock<=1.0.99999",
]

sqlalchemy_requires = ["sqlalchemy<=1.3.99999,>=0.9", "sqlalchemy-utils<=0.36.99999"]

axonserver_requires = ["axonclient<=0.0.99999"]

ray_requires = ["ray<=0.8.5", "psutil", "setproctitle"]

thespian_requires = ["thespian<=3.10.99999"]

cassandra_requires = ["cassandra-driver<=3.23.99999"]

django_requires = ["django<=3.1.99999"]

testing_requires = (
    cassandra_requires
    + sqlalchemy_requires
    + axonserver_requires
    + thespian_requires
    + ray_requires
    + django_requires
    + [
        "mock<=4.0.99999",
        "flask<=1.1.99999",
        "flask_sqlalchemy<=2.4.99",
        "uwsgi<=2.0.99999",
        # "redis<=3.5.99999",
        "celery<=5.0.99999",
        "pymysql<=0.10.99999",
        "mysql-connector-python-rf<=2.2.99999",
        "python-coveralls<=2.9.99999",
        "coverage<5.0.0",  # v5 is incompatible ATM.
        "cryptography",
        # Tests use Django with PostgreSQL.
        "psycopg2cffi<=2.8.99999" if is_pypy else "psycopg2-binary<=2.8.99999",
    ]
)

docs_requires = testing_requires + [
    "Sphinx==1.8.5",
    "python_docs_theme",
    "sphinx_py3doc_enhanced_theme",
    "sphinx_rtd_theme==0.4.3",
    "Alabaster",
    "sphinx-autobuild",
]

dev_requires = docs_requires + ["black", "mypy", "flake8", "flake8-bugbear", "isort"]

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
    name="eventsourcing",
    version=__version__,
    description="Event sourcing in Python",
    author="John Bywater",
    author_email="john.bywater@appropriatesoftware.net",
    url="https://github.com/johnbywater/eventsourcing",
    license="BSD-3-Clause",
    packages=packages,
    package_data={"eventsourcing": ["py.typed"]},
    install_requires=install_requires,
    extras_require={
        "cassandra": cassandra_requires,
        "sqlalchemy": sqlalchemy_requires,
        "axonserver": axonserver_requires,
        "axon": axonserver_requires,
        "ray": ray_requires,
        "django": django_requires,
        "test": testing_requires,
        "tests": testing_requires,
        "testing": testing_requires,
        "dev": dev_requires,
        "docs": docs_requires,
    },
    zip_safe=False,
    long_description=long_description,
    keywords=[
        "event sourcing",
        "event store",
        "domain driven design",
        "ddd",
        "cqrs",
        "cqs",
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        # 'Programming Language :: Python :: 3.5',   # we use f-strings
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
