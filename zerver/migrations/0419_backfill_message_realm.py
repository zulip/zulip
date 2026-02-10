from django.conf import settings
from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Exists, Max, OuterRef, Subquery


def backfill_message_realm(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    RECIPIENT_PERSONAL = 1
    RECIPIENT_STREAM = 2
    RECIPIENT_HUDDLE = 3

    Message = apps.get_model("zerver", "Message")
    ArchivedMessage = apps.get_model("zerver", "ArchivedMessage")
    Recipient = apps.get_model("zerver", "Recipient")
    Subscription = apps.get_model("zerver", "Subscription")
    Stream = apps.get_model("zerver", "Stream")
    UserProfile = apps.get_model("zerver", "UserProfile")
    Huddle = apps.get_model("zerver", "Huddle")

    print()

    print("Deleting dangling Recipient objects and their messages, which are inaccessible.")
    Recipient.objects.annotate(
        has_object=Exists(UserProfile.objects.filter(id=OuterRef("type_id")))
    ).filter(type=RECIPIENT_PERSONAL, has_object=False).delete()
    Recipient.objects.annotate(
        has_object=Exists(Stream.objects.filter(id=OuterRef("type_id")))
    ).filter(type=RECIPIENT_STREAM, has_object=False).delete()
    Recipient.objects.annotate(
        has_object=Exists(Huddle.objects.filter(id=OuterRef("type_id")))
    ).filter(type=RECIPIENT_HUDDLE, has_object=False).delete()

    BATCH_SIZE = 10000
    for message_model in [Message, ArchivedMessage]:
        lower_bound = 1

        max_id = message_model.objects.aggregate(Max("id"))["id__max"]
        if max_id is None:
            continue

        while lower_bound <= max_id:
            # Django's range() function is inclusive on both ends.
            upper_bound = lower_bound + BATCH_SIZE - 1
            print(f"Processing batch {lower_bound} to {upper_bound} for {message_model.__name__}")

            with transaction.atomic():
                message_model.objects.filter(
                    id__range=(lower_bound, upper_bound),
                    recipient__type=RECIPIENT_STREAM,
                ).update(
                    realm=Subquery(
                        Recipient.objects.filter(pk=OuterRef("recipient")).values("stream__realm")
                    )
                )

                # Private message to cross-realm bots are a special case, and the .realm
                # of the message should be realm of the sender.
                message_model.objects.filter(
                    id__range=(lower_bound, upper_bound),
                    recipient__type=RECIPIENT_PERSONAL,
                    recipient__userprofile__delivery_email__in=settings.CROSS_REALM_BOT_EMAILS,
                ).update(
                    realm=Subquery(
                        UserProfile.objects.filter(pk=OuterRef("sender")).values("realm")
                    )
                )

                message_model.objects.filter(
                    id__range=(lower_bound, upper_bound),
                    recipient__type=RECIPIENT_PERSONAL,
                ).exclude(
                    recipient__userprofile__delivery_email__in=settings.CROSS_REALM_BOT_EMAILS
                ).update(
                    realm=Subquery(
                        Recipient.objects.filter(pk=OuterRef("recipient")).values(
                            "userprofile__realm"
                        )
                    )
                )

                # Huddles don't have a direct way of finding their
                # realm, so we have to go through the Subscription
                # table. For huddles including a cross-realm bot, all
                # of the other users will be in the same realm, so
                # just find any of those users to get the message's realm.
                message_model.objects.filter(
                    id__range=(lower_bound, upper_bound),
                    recipient__type=RECIPIENT_HUDDLE,
                ).update(
                    realm=Subquery(
                        Subscription.objects.filter(recipient=OuterRef("recipient"))
                        .exclude(user_profile__delivery_email__in=settings.CROSS_REALM_BOT_EMAILS)
                        .values("user_profile__realm")[:1]
                    )
                )

            lower_bound += BATCH_SIZE


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0418_archivedmessage_realm_message_realm"),
    ]

    operations = [
        migrations.RunPython(
            backfill_message_realm,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
