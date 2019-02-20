def close_django_connection():
    from django.db import connection
    connection.close()


def setup_django():
    import django
    django.setup()
