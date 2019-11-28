def close_django_connection() -> None:
    from django.db import connection

    connection.close()


def setup_django() -> None:
    import django

    django.setup()
