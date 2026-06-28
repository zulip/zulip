from django.db import migrations, models
from django.conf import settings

from . import add_index


class Migration(migrations.Migration):
    atomic = settings.MIGRATE_WITH_CONCURRENT_INDICES

    dependencies = [
        ("zerver", "0527_presencesequence"),
    ]

    operations = [
        add_index(
            model_name="realmauditlog",
            index=models.Index(
                # event_type__in:
                #   AbstractRealmAuditLog.USER_CREATED,
                #   AbstractRealmAuditLog.USER_ACTIVATED,
                #   AbstractRealmAuditLog.USER_DEACTIVATED,
                #   AbstractRealmAuditLog.USER_REACTIVATED,
                condition=models.Q(("event_type__in", [101, 102, 103, 104])),
                fields=["modified_user", "event_time"],
                name="zerver_realmauditlog_user_activations_idx",
            ),
        ),
    ]
