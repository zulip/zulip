from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('zerver', '0294_remove_userprofile_pointer'),
    ]

    operations = [
        # First we change the django-created index on (realm_id, email) to be case-insensitive on the email,
        # and then we create the analogical index for (realm_id, delivery_email). The purpose of these indexes
        # is to enforce the constraint that each email address should be unique in its realm.
        # Being case-insensitive is important as the lack of this constraint has actually lead to bugs
        # where we ended up with user accounts in the same realm whose email addresses differed only
        # in character capitalization.
        migrations.RunSQL("""
            ALTER TABLE zerver_userprofile DROP CONSTRAINT zerver_userprofile_realm_id_email_13360e45_uniq;
            CREATE UNIQUE INDEX zerver_userprofile_realm_id_email_13360e45_uniq ON zerver_userprofile (realm_id, upper(email::text));
            CREATE UNIQUE INDEX zerver_userprofile_realm_id_delivery_email_uniq ON zerver_userprofile (realm_id, upper(delivery_email::text));
        """),
    ]
