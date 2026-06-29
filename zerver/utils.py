from django.contrib.postgres.operations import AddIndexConcurrently, RemoveIndexConcurrently
from django.db import migrations
from django.conf import settings


def add_index(**kwargs):
    if settings.MIGRATE_WITH_CONCURRENT_INDICES:
        return AddIndexConcurrently(**kwargs)
    else:
        return migrations.AddIndex(**kwargs)

def remove_index(**kwargs):
    if settings.MIGRATE_WITH_CONCURRENT_INDICES:
        return RemoveIndexConcurrently(**kwargs)
    else:
        return migrations.RemoveIndex(**kwargs)
