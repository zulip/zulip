from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('zerver', '0294_remove_userprofile_pointer'),
    ]

    operations = [
        # Zulip has always had case-insensitive matching for email
        # addresses on UserProfile objects.  But Django's
        # unique_together feature only supports case-sensitive
        # indexes.  So we reply the old unique_together index with a
        # new case-insensitive index.
        #
        # Further, when we created the delivery_email field, we
        # neglected to create an unique index on (realm_id,
        # delivery_email), which meant race conditions or logic bugs
        # could allow duplicate user accounts being created in
        # organizations with EMAIL_ADDRESS_VISIBILITY_ADMINS.  We
        # correct this by adding the appropriate unique index there as
        # well.
        migrations.RunSQL("""
            CREATE UNIQUE INDEX zerver_userprofile_realm_id_email_uniq ON zerver_userprofile (realm_id, upper(email::text));
            CREATE UNIQUE INDEX zerver_userprofile_realm_id_delivery_email_uniq ON zerver_userprofile (realm_id, upper(delivery_email::text));
        """),
        migrations.AlterUniqueTogether(
            name='userprofile',
            unique_together=set(),
        ),
    ]
