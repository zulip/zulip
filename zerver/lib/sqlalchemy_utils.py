from django.db import connections

if False:
    import django.db.backends.utils.CursorDebugWrapper

def get_sqlalchemy_connection():
    # type: () -> django.db.backends.utils.CursorDebugWrapper
    conn = connections['sqlalchemy']
    conn.ensure_connection()
    return conn.cursor()
