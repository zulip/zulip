from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

PLAN_TYPE_LIMITED = 2
PLAN_TYPE_STANDARD = 3
PLAN_TYPE_PLUS = 10

# CustomerPlan.LIVE_STATUS_THRESHOLD
LIVE_STATUS_THRESHOLD = 10


def backfill_realm_billing_state(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Realm = apps.get_model("zerver", "Realm")
    Customer = apps.get_model("corporate", "Customer")
    CustomerPlan = apps.get_model("corporate", "CustomerPlan")

    # Discounted pricing for non-workplace users is currently incompatible
    # with a fixed-price plan.
    realm_ids_with_fixed_price_plan = CustomerPlan.objects.filter(
        status__lt=LIVE_STATUS_THRESHOLD,
        fixed_price__isnull=False,
        customer__realm__isnull=False,
    ).values_list("customer__realm_id", flat=True)

    # Sponsored and self-hosted realms are left ineligible, which is the
    # default the field was added with.
    Realm.objects.filter(
        plan_type__in=[PLAN_TYPE_LIMITED, PLAN_TYPE_STANDARD, PLAN_TYPE_PLUS]
    ).exclude(id__in=realm_ids_with_fixed_price_plan).update(non_workplace_pricing_eligible=True)

    realm_ids_with_negotiated_discount = (
        Customer.objects.filter(
            realm__isnull=False,
        )
        .exclude(monthly_discounted_price=0, annual_discounted_price=0)
        .values_list("realm_id", flat=True)
    )
    Realm.objects.filter(
        id__in=realm_ids_with_negotiated_discount,
        plan_type__in=[PLAN_TYPE_STANDARD, PLAN_TYPE_PLUS],
    ).update(on_discounted_plan=True)


class Migration(migrations.Migration):
    dependencies = [
        ("corporate", "0048_licenseledger_external_licenses"),
        ("zerver", "0816_realm_billing_state_fields"),
    ]

    operations = [
        migrations.RunPython(
            backfill_realm_billing_state,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
