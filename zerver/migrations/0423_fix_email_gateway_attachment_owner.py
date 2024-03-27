from django.db import migrations


class Migration(migrations.Migration):
    """
    Previously, this migration had the following:

    Messages sent "as" a user via the email gateway had their
    attachments left orphan, accidentally owned by the email gateway
    bot.  Find each such orphaned attachment, and re-own it and attach
    it to the appropriate message.

    However, due to another, yet unaddressed bug, the migration may have
    run too early and been unable to address some attachment, and thus is getting
    moved to be run later in the migration tree.
    """

    dependencies = [
        ("zerver", "0422_multiuseinvite_status"),
    ]

    operations = [
        migrations.RunPython(
            migrations.RunPython.noop,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        )
    ]
