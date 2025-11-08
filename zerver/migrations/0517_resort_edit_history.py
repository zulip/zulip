from django.db import migrations

# This migration was already run as 0497 on `main`, but was
# accidentally omitted on 8.x until this point.  This is left as a
# no-op on `main`, since it has either already run -- either as this
# migration number, if the user is upgrading from 8.x, or just now as
# 0497 if the user upgraded from a prior version.


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0501_delete_dangling_usermessages"),
    ]

    operations = []
