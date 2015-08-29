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
    keywords=['eventsourcing', 'ddd', 'cqrs'],
    classifiers=[],
)
