from setuptools import setup

from eventsourcing import __version__

crypto_requires = ["pycryptodome<=3.12.99999"]
postgresql_requires = ["psycopg2<=2.9.99999"]
postgresql_dev_requires = ["psycopg2-binary<=2.9.99999"]

docs_requires = (
    postgresql_dev_requires
    + crypto_requires
    + [
        "Sphinx==4.2.0",
        "sphinx_rtd_theme==1.0.0",
    ]
)

dev_requires = docs_requires + [
    "orjson",
    "pydantic",
    "python-coveralls",
    "coverage",
    "black",
    "mypy",
    "flake8",
    "flake8-bugbear",
    "isort",
    'backports.zoneinfo;python_version<"3.9"',
]

from pathlib import Path

this_directory = Path(__file__).parent
readme_text = (this_directory / "README.md").read_text()
parts = readme_text.partition("A library for event sourcing in Python.")
long_description = "".join(parts[1:])


packages = [
    "eventsourcing",
    "eventsourcing.tests",
]


setup(
    name="eventsourcing",
    version=__version__,
    description="Event sourcing in Python",
    author="John Bywater",
    author_email="john.bywater@appropriatesoftware.net",
    url="https://github.com/pyeventsourcing/eventsourcing",
    license="BSD-3-Clause",
    packages=packages,
    package_data={"eventsourcing": ["py.typed"]},
    python_requires=">=3.7",
    install_requires=[
        'typing_extensions;python_version<"3.8"',
    ],
    extras_require={
        "postgres": postgresql_requires,
        "postgres_dev": postgresql_dev_requires,
        "crypto": crypto_requires,
        "docs": docs_requires,
        "dev": dev_requires,
    },
    zip_safe=False,
    long_description=long_description,
    long_description_content_type="text/markdown",
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
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
