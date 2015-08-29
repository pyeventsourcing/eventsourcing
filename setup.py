from distutils.core import setup

# Do we need to install mock?
install_requires_mock = False
try:
    from unittest import mock
except ImportError:
    try:
        import mock
    except ImportError:
        install_requires_mock = True


setup(
    name='eventsourcing',
    version='0.7.0',
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
    install_requires=['six'] + ['mock'] if install_requires_mock else [''],
    extras_require={
        'sqlalchemy': ['sqlalchemy'],
    },
    zip_safe=False,
    keywords=['eventsourcing', 'ddd', 'cqrs'],
    classifiers=[],
)
