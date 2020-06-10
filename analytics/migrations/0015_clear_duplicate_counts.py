from django.db import migrations
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Count, Sum


def clear_duplicate_counts(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    """This is a preparatory migration for our Analytics tables.

    The backstory is that Django's unique_together indexes do not properly
    handle the subgroup=None corner case (allowing duplicate rows that have a
    subgroup of None), which meant that in race conditions, rather than updating
    an existing row for the property/realm/time with subgroup=None, Django would
    create a duplicate row.

    In the next migration, we'll add a proper constraint to fix this bug, but
    we need to fix any existing problematic rows before we can add that constraint.

    We fix this in an appropriate fashion for each type of CountStat object; mainly
    this means deleting the extra rows, but for LoggingCountStat objects, we need to
    additionally combine the sums.
    """
    RealmCount = apps.get_model('analytics', 'RealmCount')

    realm_counts = RealmCount.objects.filter(subgroup=None).values(
        'realm_id', 'property', 'end_time').annotate(
            Count('id'), Sum('value')).filter(id__count__gt=1)

    for realm_count in realm_counts:
        realm_count.pop('id__count')
        total_value = realm_count.pop('value__sum')
        duplicate_counts = list(RealmCount.objects.filter(**realm_count))
        first_count = duplicate_counts[0]
        if realm_count['property'] in ["invites_sent::day", "active_users_log:is_bot:day"]:
            # For LoggingCountStat objects, the right fix is to combine the totals;
            # for other CountStat objects, we expect the duplicates to have the same value.
            # And so all we need to do is delete them.
            first_count.value = total_value
            first_count.save()
        to_cleanup = duplicate_counts[1:]
        for duplicate_count in to_cleanup:
            duplicate_count.delete()

class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0014_remove_fillstate_last_modified'),
    ]

    operations = [
        migrations.RunPython(clear_duplicate_counts,
                             reverse_code=migrations.RunPython.noop),
    ]
