from distutils.core import setup

setup(
    name='eventsourcing',
    version='0.2.0',
    description='Event sourcing in Python',
    author='John Bywater',
    author_email='john.bywater@appropriatesoftware.net',
    url = 'https://github.com/johnbywater/eventsourcing',
    packages=[
        'eventsourcing',
        'eventsourcing/domain',
        'eventsourcing/domain/model',
        'eventsourcing/infrastructure',
        'eventsourcingtests',
    ],
    requires=[
        'sqlalchemy',
    ],
    zip_safe=False,
    keywords=['eventsourcing', 'ddd', 'cqrs'],
    classifiers=[],
)
