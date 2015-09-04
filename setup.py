from distutils.core import setup

install_requires = ['six']

# Do we need to install mock?
install_requires_mock = False
try:
    from unittest import mock
except ImportError:
    try:
        import mock
    except ImportError:
        install_requires.append('mock')

setup(
    name='eventsourcing',
    version='0.8.0',
    description='Event sourcing in Python',
    author='John Bywater',
    author_email='john.bywater@appropriatesoftware.net',
    url = 'https://github.com/johnbywater/eventsourcing',
    packages=[
        'eventsourcing',
        'eventsourcing/application',
        'eventsourcing/domain',
        'eventsourcing/domain/model',
        'eventsourcing/infrastructure',
        'eventsourcing/infrastructure/event_sourced_repos',
        'eventsourcing/utils',
        'eventsourcingtests',
    ],
    install_requires=install_requires,
    extras_require={
        'sqlalchemy': ['sqlalchemy'],
    },
    zip_safe=False,
    long_description = """
This package provides generic domain driven design style support for event sourcing in Python.

An extensive `README file is available on GitHub <https://github.com/johnbywater/eventsourcing/blob/master/README.md>`_.
""",
    keywords=['event sourcing', 'event store', 'domain driven design', 'ddd', 'cqrs', 'cqs'],
    classifiers=[],
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Intended Audience :: Financial and Insurance Industry',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Office/Business :: Financial',
        'Topic :: Office/Business :: Financial :: Investment',
        'Topic :: Office/Business :: Financial :: Spreadsheet',
        'Topic :: Scientific/Engineering :: Information Analysis',
        'Topic :: Scientific/Engineering :: Mathematics',
        'Topic :: Software Development :: Libraries :: Python Modules',
   ],
)
