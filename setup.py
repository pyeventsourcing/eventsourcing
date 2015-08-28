from distutils.core import setup

setup(
    name='eventsourcing',
    version='0.6.0',
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
    extras_require={
        'sqlalchemy': ['sqlalchemy'],
    },
    zip_safe=False,
    keywords=['eventsourcing', 'ddd', 'cqrs'],
    classifiers=[],
)
