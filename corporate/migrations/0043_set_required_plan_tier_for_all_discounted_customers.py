from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Q


def set_required_plan_tier_for_all_discounted_customers(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    CustomerPlan = apps.get_model("corporate", "CustomerPlan")
    Customer = apps.get_model("corporate", "Customer")
    Realm = apps.get_model("zerver", "Realm")
    # Filter customers with a default_discount set.
    # Filter customer not having a required plan tier set.
    customers = Customer.objects.exclude(Q(default_discount=None) | Q(default_discount=0)).filter(
        required_plan_tier=None
    )

    CustomerPlan.TIER_CLOUD_STANDARD = 1
    CustomerPlan.TIER_CLOUD_PLUS = 2
    CustomerPlan.TIER_SELF_HOSTED_BASIC = 103
    CustomerPlan.TIER_SELF_HOSTED_BUSINESS = 104
    CustomerPlan.TIER_SELF_HOSTED_ENTERPRISE = 105
    CustomerPlan.LIVE_STATUS_THRESHOLD = 10
    CustomerPlan.NEVER_STARTED = 12

    PAID_PLANS = [
        CustomerPlan.TIER_CLOUD_STANDARD,
        CustomerPlan.TIER_CLOUD_PLUS,
        CustomerPlan.TIER_SELF_HOSTED_BASIC,
        CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
        CustomerPlan.TIER_SELF_HOSTED_ENTERPRISE,
    ]

    Realm.PLAN_TYPE_STANDARD = 3
    Realm.PLAN_TYPE_PLUS = 10

    REALM_PAID_PLANS = [
        Realm.PLAN_TYPE_STANDARD,
        Realm.PLAN_TYPE_PLUS,
    ]

    for customer in customers:
        # Assert that each customer has only paid plan which either has `status` under live threshold or never started.
        # If there are we need to first manually migrate those customer and then run this migration.
        plan = (
            CustomerPlan.objects.filter(customer__in=customers)
            .filter(tier__in=PAID_PLANS)
            .filter(
                Q(status__lt=CustomerPlan.LIVE_STATUS_THRESHOLD)
                | Q(status=CustomerPlan.NEVER_STARTED)
            )
        )

        if not plan.exists():
            # Check that realm has no paid plan.
            assert not (
                Realm.objects.filter(id=customer.realm_id)
                .filter(plan_type__in=REALM_PAID_PLANS)
                .exists()
            ), f"Customer {customer.id} has no paid plan but realm has paid plan. Manually migrate the customer."
            print(f"Customer {customer.id} has discount but no paid plan. Resetting discount.")
            customer.default_discount = None
            customer.save(update_fields=["default_discount"])
            continue

        assert (
            plan.count() == 1
        ), f"Customer {customer.id} has multiple paid plans. Manually migrate the customer."
        plan = plan.first()
        customer.required_plan_tier = plan.tier
        customer.save(update_fields=["required_plan_tier"])


class Migration(migrations.Migration):
    dependencies = [
        ("corporate", "0042_invoice_is_created_for_free_trial_upgrade_and_more"),
    ]

    operations = [
        migrations.RunPython(set_required_plan_tier_for_all_discounted_customers),
    ]
