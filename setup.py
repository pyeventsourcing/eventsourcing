from distutils.core import setup

setup(
    name='eventsourcing',
    version='0.1.0',
    packages=[
        'eventsourcing',
        'eventsourcing/domain',
        'eventsourcing/domain/model',
        'eventsourcing/infrastructure',
        'eventsourcingtests',
    ],
    zip_safe=False,
)
