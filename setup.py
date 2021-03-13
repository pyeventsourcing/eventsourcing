from distutils.core import setup

from eventsourcing import __version__

crypto_requires = ["pycryptodome<=3.9.99999"]
postgresql_requires = ["psycopg2<=2.8.99999"]
postgresql_dev_requires = ["psycopg2-binary<=2.8.99999"]

docs_requires = (
    postgresql_dev_requires
    + crypto_requires
    + [
        "Sphinx==1.8.5",
        "python_docs_theme",
        "sphinx_rtd_theme==0.4.3",
    ]
)

dev_requires = docs_requires + [
    "python-coveralls",
    "coverage",
    "black",
    "mypy",
    "flake8",
    "flake8-bugbear",
    "isort",
]

long_description = """
A library for event sourcing in Python.

`Package documentation is now available <http://eventsourcing.readthedocs.io/>`_.

`Please raise issues on GitHub <https://github.com/johnbywater/eventsourcing/issues>`_.
"""

packages = [
    "eventsourcing",
    "eventsourcing.tests",
    "eventsourcing.examples",
    "eventsourcing.examples.bankaccounts",
    "eventsourcing.examples.cargoshipping",
]


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
    install_requires=[],
    extras_require={
        "postgres": postgresql_requires,
        "postgres_dev": postgresql_dev_requires,
        "crypto": crypto_requires,
        "docs": docs_requires,
        "dev": dev_requires,
    },
    zip_safe=False,
    long_description=long_description,
    keywords=[
        "event sourcing",
        "event store",
        "domain driven design",
        "domain-driven design",
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
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
