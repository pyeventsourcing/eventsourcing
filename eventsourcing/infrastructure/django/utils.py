import six


def close_django_connection():
    if six.PY2:
        from django import db
        db.connections.close_all()
    else:
        from django.db import connection
        connection.close()


def setup_django():
    import django
    django.setup()
