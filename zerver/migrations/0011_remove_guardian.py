# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db import models, migrations, connection
from django.conf import settings

# Translate the UserProfile fields back to the old Guardian model
def unmigrate_guardian_data(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    UserProfile = apps.get_model('zerver', 'UserProfile')

    try:
        administer = Permission.objects.get(codename="administer")
    except Permission.DoesNotExist:
        administer = Permission.objects.create(codename="administer")
    try:
        api_super_user = Permission.objects.get(codename="api_super_user")
    except Permission.DoesNotExist:
        api_super_user = Permission.objects.create(codename="api_super_user")
    realm_content_type = ContentType.objects.get(app_label="zerver",
                                                 model="realm")

    # assign_perm isn't usable inside a migration, so we just directly
    # create the UserObjectPermission objects
    UserObjectPermission = apps.get_model('guardian', 'UserObjectPermission')
    for user_profile in UserProfile.objects.filter(is_realm_admin=True):
        UserObjectPermission(permission=administer,
                             user_id=user_profile.id,
                             object_pk=user_profile.realm_id,
                             content_type=realm_content_type).save()
    for user_profile in UserProfile.objects.filter(is_api_super_user=True):
        UserObjectPermission(permission=api_super_user,
                             user_id=user_profile.id,
                             object_pk=user_profile.realm_id,
                             content_type=realm_content_type).save()

# Migrate all the guardian data for which users are realm admins or
# API super users to the new fields on the UserProfile model
def migrate_guardian_data(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    UserProfile = apps.get_model('zerver', 'UserProfile')

    try:
        administer_id = Permission.objects.get(codename="administer").id
    except Permission.DoesNotExist:
        administer_id = None
    try:
        api_super_user_id = Permission.objects.get(codename="api_super_user").id
    except Permission.DoesNotExist:
        api_super_user_id = None

    # If ContentType hasn't been initialized yet, we have a new, clean
    # database and the below is not needed
    if ContentType.objects.count() == 0:
        return

    realm_content_type = ContentType.objects.get(app_label="zerver",
                                                 model="realm")

    cursor = connection.cursor()
    cursor.execute("SELECT id, object_pk, content_type_id, permission_id, user_id FROM guardian_userobjectpermission")
    for row in cursor.fetchall():
        (row_id, object_pk, content_type_id, permission_id, user_id) = row
        if content_type_id != realm_content_type.id:
            raise Exception("Unexected non-realm content type")
        user_profile = UserProfile.objects.get(id=user_id)
        if permission_id == administer_id:
            user_profile.is_realm_admin = True
        elif permission_id == api_super_user_id:
            user_profile.is_api_super_user = True
        else:
            raise Exception("Unexpected Django permission")
        user_profile.save()
    # Set the email gateway bot as an API super user so we can clean
    # up the old API_SUPER_USERS hack.
    if settings.EMAIL_GATEWAY_BOT is not None:
        try:
            email_gateway_bot = UserProfile.objects.get(email__iexact=settings.EMAIL_GATEWAY_BOT)
            email_gateway_bot.is_api_super_user = True
            email_gateway_bot.save()
        except UserProfile.DoesNotExist:
            pass

    # Delete the old permissions data in the Guardian tables; this
    # makes the reverse-migration work safely (otherwise we'd have to
    # worry about the migrate/unmigrate process racing with a user's
    # admin permissions being revoked).
    cursor.execute("DELETE FROM guardian_userobjectpermission")

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0010_delete_streamcolor'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='is_api_super_user',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='is_realm_admin',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.RunPython(migrate_guardian_data, unmigrate_guardian_data),
    ]
