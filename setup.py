from setuptools import setup, find_packages

setup(
    name='eventsourcing',
    version='1.0.1',
    description='Event sourcing in Python',
    author='John Bywater',
    author_email='john.bywater@appropriatesoftware.net',
    url = 'https://github.com/johnbywater/eventsourcing',
    packages=find_packages(),
    install_requires=[
        'singledispatch',
        'six',
        'python-dateutil',
    ],
    extras_require={
        'test': [
            'sqlalchemy',
            'mock',
            'cassandra-driver==2.6.0',
            'numpy',
        ],
        'sqlalchemy': [
            'sqlalchemy',
        ],
        'cassandra': [
            'cassandra-driver==2.6.0',
        ],
    },
    zip_safe=False,
    long_description = """
This package provides generic support for event sourcing in Python, in a 'domain driven design' style.

An extensive `README file is available on GitHub <https://github.com/johnbywater/eventsourcing/blob/master/README.md>`_.
""",
    keywords=['event sourcing', 'event store', 'domain driven design', 'ddd', 'cqrs', 'cqs'],
    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Libraries :: Python Modules',
   ],
)
