from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def fix_corrupted_named_user_group_creator(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    # A former bug in the import code could corrupt
    # NamedUserGroup.creator of some groups in pre-existing realms
    # by assigning a user from the newly imported realm to a
    # pre-existing group in an older realm.
    #
    # We take a simple approach to fixing such corrupted groups:
    # just set the creator to None for any group where the realm
    # of the creator doesn't match the realm of the group.
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE zerver_namedusergroup
            SET creator_id = NULL
            FROM zerver_userprofile
            WHERE zerver_namedusergroup.creator_id = zerver_userprofile.id
              AND zerver_userprofile.realm_id != zerver_namedusergroup.realm_id
            RETURNING
                zerver_namedusergroup.usergroup_ptr_id,
                zerver_namedusergroup.name,
                zerver_namedusergroup.realm_id,
                zerver_userprofile.id,
                zerver_userprofile.realm_id
        """)
        for (
            group_id,
            group_name,
            group_realm_id,
            old_creator_id,
            old_creator_realm_id,
        ) in cursor.fetchall():
            print(
                f"Cleared corrupted creator on NamedUserGroup id={group_id} name={group_name!r} "
                f"realm_id={group_realm_id} creator_id={old_creator_id} creator_realm_id={old_creator_realm_id}"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0795_rename_old_twitter_profile_fields"),
    ]

    operations = [
        migrations.RunPython(
            fix_corrupted_named_user_group_creator,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
