import contextlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import stripe
from django.conf import settings
from django.core.management.base import CommandParser
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from corporate.lib.stripe import (
    RealmBillingSession,
    RemoteRealmBillingSession,
    RemoteServerBillingSession,
    UpgradeRequest,
    add_months,
    sign_string,
)
from corporate.models.customers import Customer
from corporate.models.licenses import LicenseLedger
from corporate.models.plans import CustomerPlan
from scripts.lib.zulip_tools import TIMESTAMP_FORMAT
from zerver.actions.create_realm import do_create_realm
from zerver.actions.create_user import do_create_user
from zerver.actions.streams import bulk_add_subscriptions
from zerver.apps import flush_cache
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.remote_server import get_realms_info_for_push_bouncer
from zerver.lib.streams import create_stream_if_needed
from zerver.models import Realm, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm
from zilencer.models import (
    RemoteRealm,
    RemoteRealmBillingUser,
    RemoteServerBillingUser,
    RemoteZulipServer,
    RemoteZulipServerAuditLog,
)
from zilencer.views import update_remote_realm_data_for_server
from zproject.config import get_secret

current_time = timezone_now().strftime(TIMESTAMP_FORMAT)
communicate_with_stripe = get_secret("stripe_secret_key") is not None


@dataclass
class CustomerProfile:
    unique_id: str
    billing_schedule: int = CustomerPlan.BILLING_SCHEDULE_ANNUAL
    tier: int | None = None
    new_plan_tier: int | None = None
    automanage_licenses: bool = False
    status: int = CustomerPlan.ACTIVE
    sponsorship_pending: bool = False
    is_sponsored: bool = False
    card: str = ""
    charge_automatically: bool = True
    is_remote_realm: bool = False
    is_remote_server: bool = False
    renewal_date: str = current_time
    # Use (timezone_now() + timedelta(minutes=1)).strftime(TIMESTAMP_FORMAT) as `end_date` for testing.
    # `invoice_plan` is not implemented yet for remote servers and realms so no payment is generated in stripe.
    end_date: str = "2030-10-10-01-10-10"
    remote_server_plan_start_date: str = "billing_cycle_end_date"


class Command(ZulipBaseCommand):
    help = "Populate database with different types of realms that can exist."

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--only-remote-server",
            action="store_true",
            help="Whether to only run for remote servers",
        )

        parser.add_argument(
            "--only-remote-realm",
            action="store_true",
            help="Whether to only run for remote realms",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        # Create a realm for each plan type

        customer_profiles = [
            # NOTE: The unique_id has to be less than 40 characters.
            CustomerProfile(unique_id="sponsorship-pending", sponsorship_pending=True),
            CustomerProfile(
                unique_id="annual-free",
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            ),
            CustomerProfile(
                unique_id="annual-standard",
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
            ),
            CustomerProfile(
                unique_id="annual-plus",
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                tier=CustomerPlan.TIER_CLOUD_PLUS,
            ),
            CustomerProfile(
                unique_id="monthly-free",
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
            ),
            CustomerProfile(
                unique_id="monthly-standard",
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
            ),
            CustomerProfile(
                unique_id="monthly-plus",
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_PLUS,
            ),
            CustomerProfile(
                unique_id="downgrade-end-of-cycle",
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE,
            ),
            CustomerProfile(
                unique_id="standard-automanage-licenses",
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                automanage_licenses=True,
            ),
            CustomerProfile(
                unique_id="standard-automatic-card",
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                card="pm_card_visa",
            ),
            CustomerProfile(
                unique_id="standard-invoice-payment",
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                charge_automatically=False,
            ),
            CustomerProfile(
                unique_id="standard-switch-to-annual-eoc",
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE,
            ),
            CustomerProfile(
                unique_id="sponsored",
                is_sponsored=True,
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                # Customer plan might not exist for sponsored realms.
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
            ),
            CustomerProfile(
                unique_id="free-trial",
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.FREE_TRIAL,
            ),
            CustomerProfile(
                unique_id="legacy-server",
                tier=CustomerPlan.TIER_SELF_HOSTED_LEGACY,
                is_remote_server=True,
            ),
            CustomerProfile(
                unique_id="legacy-server-upgrade-scheduled",
                tier=CustomerPlan.TIER_SELF_HOSTED_LEGACY,
                status=CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END,
                new_plan_tier=CustomerPlan.TIER_SELF_HOSTED_BASIC,
                is_remote_server=True,
            ),
            CustomerProfile(
                unique_id="business-server",
                tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
                is_remote_server=True,
            ),
            CustomerProfile(
                unique_id="business-server-free-trial",
                tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
                status=CustomerPlan.FREE_TRIAL,
                is_remote_server=True,
            ),
            CustomerProfile(
                unique_id="business-server-sponsorship-pending",
                tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
                sponsorship_pending=True,
                is_remote_server=True,
            ),
            CustomerProfile(
                unique_id="self-hosted-server-sponsorship-pending",
                tier=CustomerPlan.TIER_SELF_HOSTED_BASE,
                sponsorship_pending=True,
                is_remote_server=True,
            ),
            CustomerProfile(
                unique_id="server-sponsored",
                tier=CustomerPlan.TIER_SELF_HOSTED_COMMUNITY,
                is_sponsored=True,
                is_remote_server=True,
            ),
            CustomerProfile(
                unique_id="legacy-remote-realm",
                tier=CustomerPlan.TIER_SELF_HOSTED_LEGACY,
                is_remote_realm=True,
            ),
            CustomerProfile(
                unique_id="free-tier-remote-realm",
                is_remote_realm=True,
            ),
            CustomerProfile(
                unique_id="business-remote-realm",
                tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
                is_remote_realm=True,
            ),
            CustomerProfile(
                unique_id="business-remote-free-trial",
                tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
                status=CustomerPlan.FREE_TRIAL,
                is_remote_realm=True,
            ),
            CustomerProfile(
                unique_id="business-remote-sponsorship-pending",
                tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
                sponsorship_pending=True,
                is_remote_realm=True,
            ),
            CustomerProfile(
                unique_id="remote-sponsorship-pending",
                sponsorship_pending=True,
                is_remote_realm=True,
            ),
            CustomerProfile(
                unique_id="remote-realm-sponsored",
                tier=CustomerPlan.TIER_SELF_HOSTED_COMMUNITY,
                is_sponsored=True,
                is_remote_realm=True,
            ),
            CustomerProfile(
                unique_id="basic-remote-realm",
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC,
                is_remote_realm=True,
            ),
            CustomerProfile(
                unique_id="basic-remote-free-trial",
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC,
                status=CustomerPlan.FREE_TRIAL,
                is_remote_realm=True,
            ),
        ]

        servers = []
        remote_realms = []
        for customer_profile in customer_profiles:
            if customer_profile.is_remote_server and not options.get("only_remote_realm"):
                server_conf = populate_remote_server(customer_profile)
                servers.append(server_conf)
            elif customer_profile.is_remote_realm and not options.get("only_remote_server"):
                remote_realm_conf = populate_remote_realms(customer_profile)
                remote_realms.append(remote_realm_conf)
            elif not options.get("only_remote_server") and not options.get("only_remote_realm"):
                populate_realm(customer_profile)

        print("-" * 40)
        for server in servers:
            for key, value in server.items():
                print(f"{key}: {value}")
            print("-" * 40)

        for remote_realm_conf in remote_realms:
            for key, value in remote_realm_conf.items():
                print(f"{key}: {value}")
            print("-" * 40)


def add_card_to_customer(customer: Customer) -> None:
    if not communicate_with_stripe:
        return

    assert customer.stripe_customer_id is not None
    # Set the Stripe API key
    stripe.api_key = get_secret("stripe_secret_key")

    # Create a card payment method and attach it to the customer
    payment_method = stripe.PaymentMethod.create(
        type="card",
        card={"token": "tok_visa"},
    )

    # Attach the payment method to the customer
    stripe.PaymentMethod.attach(payment_method.id, customer=customer.stripe_customer_id)

    # Set the default payment method for the customer
    stripe.Customer.modify(
        customer.stripe_customer_id,
        invoice_settings={"default_payment_method": payment_method.id},
    )


def create_plan_for_customer(customer: Customer, customer_profile: CustomerProfile) -> None:
    assert customer_profile.tier is not None
    if customer_profile.status == CustomerPlan.FREE_TRIAL:
        # 2 months free trial.
        next_invoice_date = add_months(timezone_now(), 2)
    else:
        months = 12
        if customer_profile.billing_schedule == CustomerPlan.BILLING_SCHEDULE_MONTHLY:
            months = 1
        next_invoice_date = add_months(timezone_now(), months)

    customer_plan = CustomerPlan.objects.create(
        customer=customer,
        billing_cycle_anchor=timezone_now(),
        billing_schedule=customer_profile.billing_schedule,
        tier=customer_profile.tier,
        price_per_license=1200,
        automanage_licenses=customer_profile.automanage_licenses,
        status=customer_profile.status,
        charge_automatically=customer_profile.charge_automatically,
        next_invoice_date=next_invoice_date,
    )

    LicenseLedger.objects.create(
        licenses=25,
        licenses_at_next_renewal=25,
        event_time=timezone_now(),
        is_renewal=True,
        plan=customer_plan,
    )


def populate_realm(customer_profile: CustomerProfile) -> Realm | None:
    unique_id = customer_profile.unique_id
    if customer_profile.is_remote_realm:
        plan_type = Realm.PLAN_TYPE_SELF_HOSTED
    elif customer_profile.is_sponsored:
        plan_type = Realm.PLAN_TYPE_STANDARD_FREE
    elif customer_profile.tier is None:
        plan_type = Realm.PLAN_TYPE_LIMITED
    elif customer_profile.tier == CustomerPlan.TIER_CLOUD_STANDARD:
        plan_type = Realm.PLAN_TYPE_STANDARD
    elif customer_profile.tier == CustomerPlan.TIER_CLOUD_PLUS:
        plan_type = Realm.PLAN_TYPE_PLUS
    else:
        raise AssertionError("Unexpected tier!")
    plan_name = Realm.ALL_PLAN_TYPES[plan_type]

    # Delete existing realm with this name
    with contextlib.suppress(Realm.DoesNotExist):
        get_realm(unique_id).delete()
        # Because we just deleted a bunch of objects in the database
        # directly (rather than deleting individual objects in Django,
        # in which case our post_save hooks would have flushed the
        # individual objects from memcached for us), we need to flush
        # memcached in order to ensure deleted objects aren't still
        # present in the memcached cache.
        flush_cache(None)

    realm = do_create_realm(
        string_id=unique_id,
        name=unique_id,
        description=unique_id,
        plan_type=plan_type,
    )

    # Create a user with billing access
    full_name = f"{plan_name}-admin"
    email = f"{full_name}@zulip.com"
    user = do_create_user(
        email,
        full_name,
        realm,
        full_name,
        role=UserProfile.ROLE_REALM_OWNER,
        acting_user=None,
        tos_version=settings.TERMS_OF_SERVICE_VERSION,
    )

    stream, _ = create_stream_if_needed(
        realm,
        "all",
    )

    bulk_add_subscriptions(realm, [stream], [user], acting_user=None)

    if customer_profile.is_remote_realm:
        # Remote realm billing data on their local server is irrelevant.
        return realm

    if customer_profile.sponsorship_pending or customer_profile.is_sponsored:
        # plan_type is already set correctly above for sponsored realms.
        customer = Customer.objects.create(
            realm=realm,
            sponsorship_pending=customer_profile.sponsorship_pending,
        )
        return realm

    if customer_profile.tier is None:
        return realm

    billing_session = RealmBillingSession(user)
    if communicate_with_stripe:
        # This attaches stripe_customer_id to customer.
        customer = billing_session.update_or_create_stripe_customer()
        assert customer.stripe_customer_id is not None
    else:
        customer = billing_session.update_or_create_customer()

    if customer_profile.card:
        add_card_to_customer(customer)

    create_plan_for_customer(customer, customer_profile)
    return realm


def populate_remote_server(customer_profile: CustomerProfile) -> dict[str, str]:
    unique_id = customer_profile.unique_id

    if (
        customer_profile.is_sponsored
        and customer_profile.tier == CustomerPlan.TIER_SELF_HOSTED_COMMUNITY
    ):
        plan_type = RemoteZulipServer.PLAN_TYPE_COMMUNITY
    elif customer_profile.tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY:
        plan_type = RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY
    elif customer_profile.tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS:
        plan_type = RemoteZulipServer.PLAN_TYPE_BUSINESS
    elif customer_profile.tier is CustomerPlan.TIER_SELF_HOSTED_BASE:
        plan_type = RemoteZulipServer.PLAN_TYPE_SELF_MANAGED
    else:
        raise AssertionError("Unexpected tier!")

    server_uuid = str(uuid.uuid4())
    api_key = server_uuid
    hostname = f"{unique_id}.example.com"

    # Delete existing remote server.
    RemoteZulipServer.objects.filter(hostname=hostname).delete()
    flush_cache(None)

    remote_server = RemoteZulipServer.objects.create(
        uuid=server_uuid,
        api_key=api_key,
        hostname=f"{unique_id}.example.com",
        contact_email=f"{unique_id}@example.com",
        plan_type=plan_type,
        # TODO: Save property audit log data for server.
        last_audit_log_update=timezone_now(),
    )

    RemoteZulipServerAuditLog.objects.create(
        event_type=AuditLogEventType.REMOTE_SERVER_CREATED,
        server=remote_server,
        event_time=remote_server.last_updated,
    )

    billing_user = RemoteServerBillingUser.objects.create(
        full_name="Server user",
        remote_server=remote_server,
        email=f"{unique_id}@example.com",
    )
    billing_session = RemoteServerBillingSession(remote_server, billing_user)
    if customer_profile.tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY:
        # Create customer plan for these servers for temporary period.
        renewal_date = datetime.strptime(customer_profile.renewal_date, TIMESTAMP_FORMAT).replace(
            tzinfo=timezone.utc
        )
        end_date = datetime.strptime(customer_profile.end_date, TIMESTAMP_FORMAT).replace(
            tzinfo=timezone.utc
        )
        billing_session.create_complimentary_access_plan(renewal_date, end_date)

        if not communicate_with_stripe:
            # We need to communicate with stripe to upgrade here.
            return {
                "unique_id": unique_id,
                "server_uuid": server_uuid,
                "api_key": api_key,
                "ERROR": "Need to communicate with stripe to populate this profile.",
            }

        # Scheduled server to upgrade to business plan.
        if customer_profile.status == CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END:
            # This attaches stripe_customer_id to customer.
            customer = billing_session.update_or_create_stripe_customer()
            add_card_to_customer(customer)
            seat_count = 30
            signed_seat_count, salt = sign_string(str(seat_count))
            upgrade_request = UpgradeRequest(
                billing_modality="charge_automatically",
                schedule="annual",
                signed_seat_count=signed_seat_count,
                salt=salt,
                license_management="automatic",
                licenses=seat_count,
                tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
                remote_server_plan_start_date=customer_profile.remote_server_plan_start_date,
            )
            billing_session.do_upgrade(upgrade_request)

    elif customer_profile.tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS:
        if communicate_with_stripe:
            # This attaches stripe_customer_id to customer.
            customer = billing_session.update_or_create_stripe_customer()
            assert customer.stripe_customer_id is not None
        else:
            customer = billing_session.update_or_create_customer()
        add_card_to_customer(customer)
        create_plan_for_customer(customer, customer_profile)

    if customer_profile.sponsorship_pending:
        billing_session.update_customer_sponsorship_status(True)
    elif customer_profile.is_sponsored:
        billing_session.do_change_plan_type(tier=None, is_sponsored=True)

    return {
        "unique_id": unique_id,
        "server_uuid": server_uuid,
        "api_key": api_key,
    }


def populate_remote_realms(customer_profile: CustomerProfile) -> dict[str, str]:
    # Delete existing remote realm.
    RemoteRealm.objects.filter(name=customer_profile.unique_id).delete()
    flush_cache(None)

    local_realm = populate_realm(customer_profile)
    assert local_realm is not None

    remote_server_uuid = settings.ZULIP_ORG_ID
    assert remote_server_uuid is not None
    remote_server = RemoteZulipServer.objects.filter(
        uuid=remote_server_uuid,
    ).first()

    if remote_server is None:
        raise AssertionError("Remote server not found! Please run manage.py register_server")

    update_remote_realm_data_for_server(remote_server, get_realms_info_for_push_bouncer())

    remote_realm = RemoteRealm.objects.get(uuid=local_realm.uuid)
    user = UserProfile.objects.filter(realm=local_realm).first()
    assert user is not None
    billing_user = RemoteRealmBillingUser.objects.create(
        full_name=user.full_name,
        remote_realm=remote_realm,
        user_uuid=user.uuid,
        email=user.email,
    )
    billing_session = RemoteRealmBillingSession(remote_realm, billing_user)
    # TODO: Save property audit log  data for server.
    remote_realm.server.last_audit_log_update = timezone_now()
    remote_realm.server.save(update_fields=["last_audit_log_update"])
    if communicate_with_stripe:
        # This attaches stripe_customer_id to customer.
        customer = billing_session.update_or_create_stripe_customer()
        assert customer.stripe_customer_id is not None
    else:
        customer = billing_session.update_or_create_customer()
    add_card_to_customer(customer)
    if customer_profile.tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY:
        renewal_date = datetime.strptime(customer_profile.renewal_date, TIMESTAMP_FORMAT).replace(
            tzinfo=timezone.utc
        )
        end_date = datetime.strptime(customer_profile.end_date, TIMESTAMP_FORMAT).replace(
            tzinfo=timezone.utc
        )
        billing_session.create_complimentary_access_plan(renewal_date, end_date)
    elif customer_profile.tier is not None:
        billing_session.do_change_plan_type(
            tier=customer_profile.tier, is_sponsored=customer_profile.is_sponsored
        )
        if not customer_profile.is_sponsored:
            create_plan_for_customer(customer, customer_profile)

    if customer_profile.sponsorship_pending:
        billing_session.update_customer_sponsorship_status(True)

    return {
        "unique_id": customer_profile.unique_id,
        "login_url": local_realm.url + "/self-hosted-billing/",
    }
