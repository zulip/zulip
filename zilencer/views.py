import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.headerregistry import Address
from typing import Annotated, Any, TypedDict, TypeVar
from urllib.parse import urljoin, urlsplit
from uuid import UUID

import orjson
import requests.exceptions
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import IntegrityError, transaction
from django.db.models import Model
from django.db.models.constants import OnConflict
from django.http import HttpRequest, HttpResponse
from django.utils.crypto import constant_time_compare, get_random_string
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import gettext as err_
from django.views.decorators.csrf import csrf_exempt
from dns import resolver as dns_resolver
from dns.exception import DNSException
from nacl.encoding import Base64Encoder
from nacl.exceptions import CryptoError
from nacl.public import PrivateKey, SealedBox
from pydantic import BaseModel, ConfigDict, Json, StringConstraints, model_validator
from pydantic import ValidationError as PydanticValidationError
from pydantic.functional_validators import AfterValidator

from analytics.lib.counts import (
    BOUNCER_ONLY_REMOTE_COUNT_STAT_PROPERTIES,
    COUNT_STATS,
    LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER,
    REMOTE_INSTALLATION_COUNT_STATS,
    do_increment_logging_stat,
)
from corporate.models.customers import get_customer_by_remote_realm
from corporate.models.plans import CustomerPlan, get_current_plan_by_customer
from zerver.decorator import require_post
from zerver.lib.email_validation import validate_is_not_disposable
from zerver.lib.exceptions import (
    ErrorCode,
    InvalidBouncerPublicKeyError,
    InvalidEncryptedPushRegistrationError,
    JsonableError,
    MissingRemoteRealmError,
    RateLimitedError,
    RemoteRealmServerMismatchError,
    RemoteServerDeactivatedError,
    RequestExpiredError,
)
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.push_notifications import (
    PUSH_REGISTRATION_LIVENESS_TIMEOUT,
    HostnameAlreadyInUseBouncerError,
    InvalidRemotePushDeviceTokenError,
    UserPushIdentityCompat,
    send_android_push_notification,
    send_apple_push_notification,
    send_test_push_notification_directly_to_devices,
    validate_token,
)
from zerver.lib.queue import queue_event_on_commit
from zerver.lib.rate_limiter import rate_limit_endpoint_absolute
from zerver.lib.remote_server import (
    InstallationCountDataForAnalytics,
    RealmAuditLogDataForAnalytics,
    RealmCountDataForAnalytics,
    RealmDataForAnalytics,
)
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.send_email import EMAIL_DATE_FORMAT, FromAddress
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.typed_endpoint import (
    ApnsAppId,
    JsonBodyPayload,
    RequiredStringConstraint,
    typed_endpoint,
    typed_endpoint_without_parameters,
)
from zerver.lib.typed_endpoint_validators import check_string_fixed_length
from zerver.lib.types import RemoteRealmDictValue
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import DisposableEmailError, Realm
from zilencer.auth import (
    InvalidZulipServerKeyError,
    generate_registration_transfer_verification_secret,
    validate_registration_transfer_verification_secret,
)
from zilencer.lib.remote_counts import MissingDataError
from zilencer.models import (
    RemoteInstallationCount,
    RemotePushDevice,
    RemotePushDeviceToken,
    RemoteRealm,
    RemoteRealmAuditLog,
    RemoteRealmCount,
    RemoteZulipServer,
    RemoteZulipServerAuditLog,
)

logger = logging.getLogger(__name__)


def validate_uuid(uuid: str) -> None:
    try:
        uuid_object = UUID(uuid, version=4)
        # The UUID initialization under some circumstances will modify the uuid
        # string to create a valid UUIDv4, instead of raising a ValueError.
        # The submitted uuid needing to be modified means it's invalid, so
        # we need to check for that condition.
        if str(uuid_object) != uuid:
            raise ValidationError(err_("Invalid UUID"))
    except ValueError:
        raise ValidationError(err_("Invalid UUID"))


def validate_bouncer_token_request(token: str, kind: int) -> None:
    if kind not in [RemotePushDeviceToken.APNS, RemotePushDeviceToken.FCM]:
        raise JsonableError(err_("Invalid token type"))
    validate_token(token, kind)


@csrf_exempt
@require_post
@typed_endpoint_without_parameters
def deactivate_remote_server(
    request: HttpRequest,
    remote_server: RemoteZulipServer,
) -> HttpResponse:
    from corporate.lib.stripe import RemoteServerBillingSession, do_deactivate_remote_server

    billing_session = RemoteServerBillingSession(remote_server)
    do_deactivate_remote_server(remote_server, billing_session)
    return json_success(request)


def validate_hostname_or_raise_error(hostname: str) -> None:
    """
    Validate that the argument is a valid hostname to be registered
    with the bouncer.

    Note: The hostname is allowed to contain a port number, as some
    registration do take this form and without the port we wouldn't
    actually know how to make requests to the server.
    """
    try:
        # We perform basic validation in two steps:
        # 1. urlsplit doesn't do any proper validation, but parses the string
        #    and ensures that there are no extra components (e.g., path, query, fragment).
        # 2. Once we know that the string is a clean netloc, we pass that do Django's
        #    URLValidator for validation.
        parsed = urlsplit(f"http://{hostname}")

        if parsed.path or parsed.query or parsed.fragment:
            raise JsonableError(
                _("{hostname} contains invalid components (e.g., path, query, fragment).").format(
                    hostname=hostname
                )
            )
        url_validator = URLValidator()
        url_validator("http://" + hostname)
    except ValidationError:
        raise JsonableError(_("{hostname} is not a valid hostname").format(hostname=hostname))


@csrf_exempt
@require_post
@typed_endpoint
def transfer_remote_server_registration(request: HttpRequest, *, hostname: str) -> HttpResponse:
    validate_hostname_or_raise_error(hostname)

    if not RemoteZulipServer.objects.filter(hostname=hostname).exists():
        raise JsonableError(_("{hostname} not yet registered").format(hostname=hostname))

    verification_secret = generate_registration_transfer_verification_secret(hostname)
    return json_success(
        request,
        data={
            "verification_secret": verification_secret,
        },
    )


@csrf_exempt
@require_post
@typed_endpoint
def register_remote_server(
    request: HttpRequest,
    *,
    zulip_org_id: Annotated[
        str,
        RequiredStringConstraint,
        AfterValidator(lambda s: check_string_fixed_length(s, RemoteZulipServer.UUID_LENGTH)),
    ],
    zulip_org_key: Annotated[
        str,
        RequiredStringConstraint,
        AfterValidator(lambda s: check_string_fixed_length(s, RemoteZulipServer.API_KEY_LENGTH)),
    ],
    hostname: Annotated[str, StringConstraints(max_length=RemoteZulipServer.HOSTNAME_MAX_LENGTH)],
    contact_email: str,
    new_org_key: Annotated[
        str | None,
        RequiredStringConstraint,
        AfterValidator(lambda s: check_string_fixed_length(s, RemoteZulipServer.API_KEY_LENGTH)),
    ] = None,
) -> HttpResponse:
    # StringConstraints validated the field lengths, but we still need to
    # validate the format of these fields.
    validate_hostname_or_raise_error(hostname)

    try:
        validate_email(contact_email)
    except ValidationError as e:
        raise JsonableError(e.message)

    # We don't want to allow disposable domains for contact_email either
    try:
        validate_is_not_disposable(contact_email)
    except DisposableEmailError:
        raise JsonableError(_("Please use your real email address."))

    contact_email_domain = Address(addr_spec=contact_email).domain.lower()
    if contact_email_domain == "example.com":
        raise JsonableError(_("Invalid email address."))

    # Check if the domain has an MX record
    resolver = dns_resolver.Resolver()
    resolver.timeout = 3
    dns_mx_check_successful = False
    try:
        if resolver.resolve(contact_email_domain, "MX"):
            dns_mx_check_successful = True
    except DNSException:
        pass
    if not dns_mx_check_successful:
        # Check if the A/AAAA exist, for better error reporting
        try:
            resolver.resolve_name(contact_email_domain)
            raise JsonableError(
                _("{domain} is invalid because it does not have any MX records").format(
                    domain=contact_email_domain
                )
            )
        except DNSException:
            raise JsonableError(_("{domain} does not exist").format(domain=contact_email_domain))

    try:
        validate_uuid(zulip_org_id)
    except ValidationError as e:
        raise JsonableError(e.message)

    try:
        remote_server = RemoteZulipServer.objects.get(uuid=zulip_org_id)
    except RemoteZulipServer.DoesNotExist:
        remote_server = None

    if remote_server is not None:
        if not constant_time_compare(remote_server.api_key, zulip_org_key):
            raise InvalidZulipServerKeyError(zulip_org_id)

        if remote_server.deactivated:
            raise RemoteServerDeactivatedError

    if remote_server is None and RemoteZulipServer.objects.filter(hostname=hostname).exists():
        raise HostnameAlreadyInUseBouncerError(hostname)

    with transaction.atomic(durable=True):
        if remote_server is None:
            created = True
            remote_server = RemoteZulipServer.objects.create(
                uuid=zulip_org_id,
                hostname=hostname,
                contact_email=contact_email,
                api_key=zulip_org_key,
                last_request_datetime=timezone_now(),
            )
            RemoteZulipServerAuditLog.objects.create(
                event_type=AuditLogEventType.REMOTE_SERVER_CREATED,
                server=remote_server,
                event_time=remote_server.last_updated,
            )
        else:
            created = False
            remote_server.hostname = hostname
            remote_server.contact_email = contact_email
            if new_org_key is not None:
                remote_server.api_key = new_org_key

            remote_server.last_request_datetime = timezone_now()
            remote_server.save()

    return json_success(request, data={"created": created})


class RegistrationTransferVerificationSession(OutgoingSession):
    def __init__(self) -> None:
        # The generous timeout and retries here are likely to be unnecessary; a functional Zulip server should
        # respond instantly.
        super().__init__(role="verify_registration_transfer_challenge", timeout=5, max_retries=3)


class EndpointUsageRateLimitError(JsonableError):
    code = ErrorCode.RATE_LIMIT_HIT
    http_status_code = 429


@csrf_exempt
@typed_endpoint
def verify_registration_transfer_challenge_ack_endpoint(
    request: HttpRequest,
    *,
    hostname: str,
    access_token: str,
) -> HttpResponse:
    """
    The host should POST to this endpoint to announce it is ready to serve the received
    secret at {hostname}/zulip-services/verify/{access_token}.
    The access_token is randomly generated by the host in order to prevent 3rd parties
    from accessing the verification secret served at that URL.

    If we successfully verify the secret, we will send the registration credentials
    to the host, completing the whole flow.
    """

    try:
        # This endpoint is at risk of being used to spam another server with our requests,
        # or to freeze up our Django processes by making them wait for timeouts on the
        # requests triggered here.
        # Since this is an extremely low-traffic endpoint, we just put an absolute limit on
        # how many times it can be called in a given time period. There's little value for an
        # attacker to fill up the bucket here, and issues can be handled adequately by
        # manual intervention.
        if settings.RATE_LIMITING:
            rate_limit_endpoint_absolute("verify_registration_transfer_challenge_ack_endpoint")
    except RateLimitedError:
        # This rate limit being hit means we've either set the limits too low for legitimate use,
        # or the endpoint is being spammed. Ideally, we want this endpoint to always be operational
        # so this deserves logging a warning.
        logger.warning(
            "Rate limit exceeded for verify_registration_transfer_challenge_ack_endpoint"
        )
        raise EndpointUsageRateLimitError(
            _(
                "The global limits on recent usage of this endpoint have been reached."
                " Please try again later or reach out to {support_email} for assistance."
            ).format(support_email=FromAddress.SUPPORT)
        )

    try:
        remote_server = RemoteZulipServer.objects.get(hostname=hostname)
    except RemoteZulipServer.DoesNotExist:
        raise JsonableError(_("Registration not found for this hostname"))

    session = RegistrationTransferVerificationSession()
    url = urljoin(f"https://{hostname}", f"/api/v1/zulip-services/verify/{access_token}/")

    exception_and_error_message: tuple[Exception, str] | None = None
    try:
        response = session.get(url)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if check_transfer_challenge_response_secret_not_prepared(e.response):
            logger.info("verify_registration_transfer:host:%s|secret_not_prepared", hostname)
            raise JsonableError(_("The host reported it has no verification secret."))

        error_message = _("Error response received from the host: {status_code}").format(
            status_code=response.status_code
        )
        exception_and_error_message = (e, error_message)
    except requests.exceptions.SSLError as e:
        error_message = "SSL error occurred while communicating with the host."
        exception_and_error_message = (e, error_message)
    except requests.exceptions.ConnectionError as e:
        error_message = "Connection error occurred while communicating with the host."
        exception_and_error_message = (e, error_message)
    except requests.exceptions.Timeout as e:
        error_message = "The request timed out while communicating with the host."
        exception_and_error_message = (e, error_message)
    except requests.exceptions.RequestException as e:
        error_message = "An error occurred while communicating with the host."
        exception_and_error_message = (e, error_message)

    if exception_and_error_message is not None:
        exception, error_message = exception_and_error_message
        logger.info("verify_registration_transfer:host:%s|exception:%s", hostname, exception)
        raise JsonableError(error_message)

    data = response.json()
    verification_secret = data["verification_secret"]
    validate_registration_transfer_verification_secret(verification_secret, hostname)

    logger.info("verify_registration_transfer:host:%s|success", hostname)
    new_secret_key = get_random_string(RemoteZulipServer.API_KEY_LENGTH)
    with transaction.atomic(durable=True):
        remote_server.api_key = new_secret_key
        remote_server.save(update_fields=["api_key"])

        RemoteZulipServerAuditLog.objects.create(
            event_type=AuditLogEventType.REMOTE_SERVER_REGISTRATION_TRANSFERRED,
            server=remote_server,
            event_time=timezone_now(),
        )

    return json_success(
        request,
        data={"zulip_org_id": str(remote_server.uuid), "zulip_org_key": new_secret_key},
    )


def check_transfer_challenge_response_secret_not_prepared(response: requests.Response) -> bool:
    secret_not_prepared = False
    try:
        secret_not_prepared = (
            response.status_code == 400
            and response.json()["code"] == "REMOTE_SERVER_VERIFICATION_SECRET_NOT_PREPARED"
        )
    except Exception:  # nocoverage
        return False
    return secret_not_prepared


@typed_endpoint
def register_remote_push_device(
    request: HttpRequest,
    server: RemoteZulipServer,
    *,
    user_id: Json[int] | None = None,
    user_uuid: str | None = None,
    realm_uuid: str | None = None,
    token: Annotated[str, RequiredStringConstraint],
    token_kind: Json[int],
    ios_app_id: ApnsAppId | None = None,
) -> HttpResponse:
    validate_bouncer_token_request(token, token_kind)
    if token_kind == RemotePushDeviceToken.APNS and ios_app_id is None:
        raise JsonableError(_("Missing ios_app_id"))

    if user_id is None and user_uuid is None:
        raise JsonableError(_("Missing user_id or user_uuid"))
    if user_id is not None and user_uuid is not None:
        kwargs: dict[str, object] = {"user_uuid": user_uuid, "user_id": None}
        # Delete pre-existing user_id registration for this user+device to avoid
        # duplication. Further down, uuid registration will be created.
        RemotePushDeviceToken.objects.filter(
            server=server, token=token, kind=token_kind, user_id=user_id
        ).delete()
    else:
        # One of these is None, so these kwargs will lead to a proper registration
        # of either user_id or user_uuid type
        kwargs = {"user_id": user_id, "user_uuid": user_uuid}

    if realm_uuid is not None:
        # Servers 8.0+ also send the realm.uuid of the user.
        assert isinstance(user_uuid, str), (
            "Servers new enough to send realm_uuid, should also have user_uuid"
        )
        remote_realm = get_remote_realm_helper(request, server, realm_uuid)
        if remote_realm is not None:
            # We want to associate the RemotePushDeviceToken with the RemoteRealm.
            kwargs["remote_realm_id"] = remote_realm.id

            remote_realm.last_request_datetime = timezone_now()
            remote_realm.save(update_fields=["last_request_datetime"])

    RemotePushDeviceToken.objects.bulk_create(
        [
            RemotePushDeviceToken(
                server=server,
                kind=token_kind,
                token=token,
                ios_app_id=ios_app_id,
                # last_updated is to be renamed to date_created.
                last_updated=timezone_now(),
                **kwargs,
            ),
        ],
        ignore_conflicts=True,
    )

    return json_success(request)


class PushRegistration(BaseModel):
    token: str
    token_kind: str
    ios_app_id: ApnsAppId | None = None
    timestamp: int

    def is_valid_token(self) -> bool:
        if self.token == "" or len(self.token) > 4096:
            # Invalid token length
            return False

        if self.token_kind == RemotePushDevice.TokenKind.APNS:
            try:
                bytes.fromhex(self.token)
            except ValueError:
                return False
        return True

    @model_validator(mode="after")
    def validate_terms(self) -> "PushRegistration":
        if self.token_kind not in [RemotePushDevice.TokenKind.APNS, RemotePushDevice.TokenKind.FCM]:
            raise ValueError("Invalid token_kind")

        if self.token_kind == RemotePushDevice.TokenKind.APNS and self.ios_app_id is None:
            raise ValueError("Missing ios_app_id")

        if self.token_kind == RemotePushDevice.TokenKind.FCM and self.ios_app_id is not None:
            raise ValueError(
                f"For token_kind={RemotePushDevice.TokenKind.FCM}, ios_app_id should be null"
            )

        if not self.is_valid_token():
            raise ValueError("Invalid token")

        return self


def do_register_remote_push_device(
    bouncer_public_key: str,
    encrypted_push_registration: str,
    push_account_id: int,
    *,
    realm: Realm | None = None,
    remote_realm: RemoteRealm | None = None,
) -> int:
    assert (realm is None) ^ (remote_realm is None)

    assert settings.PUSH_REGISTRATION_ENCRYPTION_KEYS
    if bouncer_public_key not in settings.PUSH_REGISTRATION_ENCRYPTION_KEYS:
        raise InvalidBouncerPublicKeyError

    # Decrypt push_registration
    bouncer_private_key: str = settings.PUSH_REGISTRATION_ENCRYPTION_KEYS[bouncer_public_key]
    private_key = PrivateKey(bouncer_private_key.encode("utf-8"), encoder=Base64Encoder)
    unseal_box = SealedBox(private_key)

    try:
        push_registration_bytes = unseal_box.decrypt(
            Base64Encoder.decode(encrypted_push_registration.encode("utf-8"))
        )
    except (TypeError, CryptoError):
        raise InvalidEncryptedPushRegistrationError

    try:
        push_registration = PushRegistration.model_validate_json(push_registration_bytes)
    except PydanticValidationError:
        raise InvalidEncryptedPushRegistrationError

    if (
        datetime_to_timestamp(timezone_now()) - push_registration.timestamp
        > PUSH_REGISTRATION_LIVENESS_TIMEOUT
    ):
        raise RequestExpiredError

    # If already registered, return the device_id.
    # The query uses the unique index created by the
    # 'unique_remote_push_device_push_account_id_token' constraint.
    remote_push_device = RemotePushDevice.objects.filter(
        token=push_registration.token, push_account_id=push_account_id
    ).first()
    if remote_push_device:
        return remote_push_device.device_id

    remote_push_device = RemotePushDevice.objects.create(
        realm=realm,
        remote_realm=remote_realm,
        token=push_registration.token,
        token_kind=push_registration.token_kind,
        push_account_id=push_account_id,
        ios_app_id=push_registration.ios_app_id,
    )
    return remote_push_device.device_id


@typed_endpoint
def register_remote_push_device_for_e2ee_push_notification(
    request: HttpRequest,
    server: RemoteZulipServer,
    *,
    realm_uuid: str,
    push_account_id: Json[int],
    encrypted_push_registration: str,
    bouncer_public_key: str,
) -> HttpResponse:
    remote_realm = get_remote_realm_helper(request, server, realm_uuid)
    if remote_realm is None:
        raise MissingRemoteRealmError
    else:
        remote_realm.last_request_datetime = timezone_now()
        remote_realm.save(update_fields=["last_request_datetime"])

    device_id = do_register_remote_push_device(
        bouncer_public_key,
        encrypted_push_registration,
        push_account_id,
        remote_realm=remote_realm,
    )

    return json_success(request, {"device_id": device_id})


@typed_endpoint
def unregister_remote_push_device(
    request: HttpRequest,
    server: RemoteZulipServer,
    *,
    token: Annotated[str, RequiredStringConstraint],
    token_kind: Json[int],
    user_id: Json[int] | None = None,
    user_uuid: str | None = None,
    realm_uuid: str | None = None,
) -> HttpResponse:
    validate_bouncer_token_request(token, token_kind)
    user_identity = UserPushIdentityCompat(user_id=user_id, user_uuid=user_uuid)

    update_remote_realm_last_request_datetime_helper(request, server, realm_uuid, user_uuid)

    (num_deleted, ignored) = RemotePushDeviceToken.objects.filter(
        user_identity.filter_q(), token=token, kind=token_kind, server=server
    ).delete()
    if num_deleted == 0:
        raise JsonableError(err_("Token does not exist"))

    return json_success(request)


@typed_endpoint
def unregister_all_remote_push_devices(
    request: HttpRequest,
    server: RemoteZulipServer,
    *,
    user_id: Json[int] | None = None,
    user_uuid: str | None = None,
    realm_uuid: str | None = None,
) -> HttpResponse:
    user_identity = UserPushIdentityCompat(user_id=user_id, user_uuid=user_uuid)

    update_remote_realm_last_request_datetime_helper(request, server, realm_uuid, user_uuid)

    RemotePushDeviceToken.objects.filter(user_identity.filter_q(), server=server).delete()
    return json_success(request)


def update_remote_realm_last_request_datetime_helper(
    request: HttpRequest,
    server: RemoteZulipServer,
    realm_uuid: str | None,
    user_uuid: str | None,
) -> None:
    if realm_uuid is not None:
        assert user_uuid is not None
        remote_realm = get_remote_realm_helper(request, server, realm_uuid)
        if remote_realm is not None:
            remote_realm.last_request_datetime = timezone_now()
            remote_realm.save(update_fields=["last_request_datetime"])


def delete_duplicate_registrations(
    registrations: list[RemotePushDeviceToken], server_id: int, user_id: int, user_uuid: str
) -> list[RemotePushDeviceToken]:
    """
    When migrating to support registration by UUID, we introduced a bug where duplicate
    registrations for the same device+user could be created - one by user_id and one by
    user_uuid. Given no good way of detecting these duplicates at database level, we need to
    take advantage of the fact that when a remote server sends a push notification request
    to us, it sends both user_id and user_uuid of the user.
    See https://github.com/zulip/zulip/issues/24969 for reference.

    This function, knowing the user_id and user_uuid of the user, can detect duplicates
    and delete the legacy user_id registration if appropriate.

    Return the list of registrations with the user_id-based duplicates removed.
    """

    # All registrations passed here should be of the same kind (apple vs android).
    assert len({registration.kind for registration in registrations}) == 1
    kind = registrations[0].kind

    tokens_counter = Counter(device.token for device in registrations)

    tokens_to_deduplicate = []
    for key in tokens_counter:
        if tokens_counter[key] <= 1:
            continue
        if tokens_counter[key] > 2:
            raise AssertionError(
                f"More than two registrations for token {key} for user id:{user_id} uuid:{user_uuid}, shouldn't be possible"
            )
        assert tokens_counter[key] == 2
        tokens_to_deduplicate.append(key)

    if not tokens_to_deduplicate:
        return registrations

    logger.info(
        "Deduplicating push registrations for server id:%s user id:%s uuid:%s and tokens:%s",
        server_id,
        user_id,
        user_uuid,
        sorted(tokens_to_deduplicate),
    )
    RemotePushDeviceToken.objects.filter(
        token__in=tokens_to_deduplicate, kind=kind, server_id=server_id, user_id=user_id
    ).delete()

    deduplicated_registrations_to_return = []
    for registration in registrations:
        if registration.token in tokens_to_deduplicate and registration.user_id is not None:
            # user_id registrations are the ones we deleted
            continue
        deduplicated_registrations_to_return.append(registration)

    return deduplicated_registrations_to_return


class TestNotificationPayload(BaseModel):
    token: str
    token_kind: int
    user_id: int
    user_uuid: str
    realm_uuid: str | None = None
    base_payload: dict[str, Any]

    model_config = ConfigDict(extra="forbid")


@typed_endpoint
def remote_server_send_test_notification(
    request: HttpRequest,
    server: RemoteZulipServer,
    *,
    payload: JsonBodyPayload[TestNotificationPayload],
) -> HttpResponse:
    token = payload.token
    token_kind = payload.token_kind

    user_id = payload.user_id
    user_uuid = payload.user_uuid
    realm_uuid = payload.realm_uuid

    # The remote server only sends the base payload with basic user and server info,
    # and the actual format of the test notification is defined on the bouncer, as that
    # gives us the flexibility to modify it freely, without relying on other servers
    # upgrading.
    base_payload = payload.base_payload

    # This is a new endpoint, so it can assume it will only be used by newer
    # servers that will send user both UUID and ID.
    user_identity = UserPushIdentityCompat(user_id=user_id, user_uuid=user_uuid)

    update_remote_realm_last_request_datetime_helper(request, server, realm_uuid, user_uuid)

    try:
        device = RemotePushDeviceToken.objects.get(
            user_identity.filter_q(), token=token, kind=token_kind, server=server
        )
    except RemotePushDeviceToken.DoesNotExist:
        raise InvalidRemotePushDeviceTokenError

    send_test_push_notification_directly_to_devices(
        user_identity, [device], base_payload, remote=server
    )
    return json_success(request)


def get_remote_realm_helper(
    request: HttpRequest,
    server: RemoteZulipServer,
    realm_uuid: str,
) -> RemoteRealm | None:
    """
    Tries to fetch RemoteRealm for the given realm_uuid and server. Otherwise,
    returns None and logs what happened using request and user_uuid args to make
    the output more informative.
    """

    try:
        remote_realm = RemoteRealm.objects.get(uuid=realm_uuid)
    except RemoteRealm.DoesNotExist:
        logger.info(
            "%s: Received request for unknown realm %s, server %s",
            request.path,
            realm_uuid,
            server.id,
        )
        return None

    if remote_realm.server_id != server.id:
        logger.warning(
            "%s: Realm %s exists, but not registered to server %s",
            request.path,
            realm_uuid,
            server.id,
        )
        raise RemoteRealmServerMismatchError

    return remote_realm


class OldZulipServerError(JsonableError):
    code = ErrorCode.INVALID_ZULIP_SERVER

    def __init__(self, msg: str) -> None:
        self._msg: str = msg


class PushNotificationsDisallowedError(JsonableError):
    code = ErrorCode.PUSH_NOTIFICATIONS_DISALLOWED

    def __init__(self, reason: str) -> None:
        msg = _(
            "Your plan doesn't allow sending push notifications. Reason provided by the server: {reason}"
        ).format(reason=reason)
        super().__init__(msg)


class RemoteServerNotificationPayload(BaseModel):
    user_id: int | None = None
    user_uuid: str | None = None
    realm_uuid: str | None = None
    gcm_payload: dict[str, Any] = {}
    apns_payload: dict[str, Any] = {}
    gcm_options: dict[str, Any] = {}

    android_devices: list[str] = []
    apple_devices: list[str] = []


@typed_endpoint
def remote_server_notify_push(
    request: HttpRequest,
    server: RemoteZulipServer,
    *,
    payload: JsonBodyPayload[RemoteServerNotificationPayload],
) -> HttpResponse:
    from corporate.lib.stripe import get_push_status_for_remote_request

    user_id = payload.user_id
    user_uuid = payload.user_uuid
    user_identity = UserPushIdentityCompat(user_id, user_uuid)

    gcm_payload = payload.gcm_payload
    apns_payload = payload.apns_payload
    gcm_options = payload.gcm_options

    realm_uuid = payload.realm_uuid
    remote_realm = None
    if realm_uuid is not None:
        assert isinstance(user_uuid, str), (
            "Servers new enough to send realm_uuid, should also have user_uuid"
        )
        remote_realm = get_remote_realm_helper(request, server, realm_uuid)

    push_status = get_push_status_for_remote_request(server, remote_realm)
    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    log_data["extra"] = f"[can_push={push_status.can_push}/{push_status.message}]"
    if not push_status.can_push:
        if server.last_api_feature_level is None:
            raise OldZulipServerError(_("Your plan doesn't allow sending push notifications."))
        else:
            reason = push_status.message
            raise PushNotificationsDisallowedError(reason=reason)

    android_devices = list(
        RemotePushDeviceToken.objects.filter(
            user_identity.filter_q(),
            kind=RemotePushDeviceToken.FCM,
            server=server,
        ).order_by("id")
    )
    if android_devices and user_id is not None and user_uuid is not None:
        android_devices = delete_duplicate_registrations(
            android_devices, server.id, user_id, user_uuid
        )

    apple_devices = list(
        RemotePushDeviceToken.objects.filter(
            user_identity.filter_q(),
            kind=RemotePushDeviceToken.APNS,
            server=server,
        ).order_by("id")
    )
    if apple_devices and user_id is not None and user_uuid is not None:
        apple_devices = delete_duplicate_registrations(apple_devices, server.id, user_id, user_uuid)

    remote_queue_latency: str | None = None
    sent_time: float | int | None = gcm_payload.get(
        # TODO/compatibility: This could be a lot simpler if not for pre-5.0 Zulip servers
        # that had an older format. Future implementation:
        #     "time", apns_payload["custom"]["zulip"].get("time")
        "time",
        apns_payload.get("custom", {}).get("zulip", {}).get("time"),
    )
    if sent_time is not None:
        if isinstance(sent_time, int):
            # The 'time' field only used to have whole-integer
            # granularity, so if so we only report with
            # whole-second granularity
            remote_queue_latency = str(int(timezone_now().timestamp()) - sent_time)
        else:
            remote_queue_latency = f"{timezone_now().timestamp() - sent_time:.3f}"
        logger.info(
            "Remote queuing latency for %s:%s is %s seconds",
            server.uuid,
            user_identity,
            remote_queue_latency,
        )

    logger.info(
        "Sending mobile push notifications for remote user %s:%s: %s via FCM devices, %s via APNs devices",
        server.uuid,
        user_identity,
        len(android_devices),
        len(apple_devices),
    )
    do_increment_logging_stat(
        server,
        REMOTE_INSTALLATION_COUNT_STATS["mobile_pushes_received::day"],
        None,
        timezone_now(),
        increment=len(android_devices) + len(apple_devices),
    )
    if remote_realm is not None:
        ensure_devices_set_remote_realm(
            android_devices=android_devices, apple_devices=apple_devices, remote_realm=remote_realm
        )
        do_increment_logging_stat(
            remote_realm,
            COUNT_STATS["mobile_pushes_received::day"],
            None,
            timezone_now(),
            increment=len(android_devices) + len(apple_devices),
        )

        remote_realm.last_request_datetime = timezone_now()
        remote_realm.save(update_fields=["last_request_datetime"])

    # Truncate incoming pushes to 200, due to APNs maximum message
    # sizes; see handle_remove_push_notification for the version of
    # this for notifications generated natively on the server.  We
    # apply this to remote-server pushes in case they predate that
    # commit.
    def truncate_payload(payload: dict[str, Any]) -> dict[str, Any]:
        MAX_MESSAGE_IDS = 200
        if payload and payload.get("event") == "remove" and payload.get("zulip_message_ids"):
            ids = [int(id) for id in payload["zulip_message_ids"].split(",")]
            truncated_ids = sorted(ids)[-MAX_MESSAGE_IDS:]
            payload["zulip_message_ids"] = ",".join(str(id) for id in truncated_ids)
        return payload

    # The full request must complete within 30s, the timeout set by
    # Zulip remote hosts for push notification requests (see
    # PushBouncerSession).  The timeouts in the FCM and APNS codepaths
    # must be set accordingly; see send_android_push_notification and
    # send_apple_push_notification.
    # TODO: This limit can be slightly exceeded now after changing the library
    # used for sending FCM notifications. This is pending adjustment after
    # getting some data on the behavior of the new API.

    gcm_payload = truncate_payload(gcm_payload)
    android_successfully_delivered = send_android_push_notification(
        user_identity, android_devices, gcm_payload, gcm_options, remote=server
    )

    if isinstance(apns_payload.get("custom"), dict) and isinstance(
        apns_payload["custom"].get("zulip"), dict
    ):
        apns_payload["custom"]["zulip"] = truncate_payload(apns_payload["custom"]["zulip"])
    apple_successfully_delivered = send_apple_push_notification(
        user_identity, apple_devices, apns_payload, remote=server
    )

    do_increment_logging_stat(
        server,
        REMOTE_INSTALLATION_COUNT_STATS["mobile_pushes_forwarded::day"],
        None,
        timezone_now(),
        increment=android_successfully_delivered + apple_successfully_delivered,
    )

    remote_realm_dict: RemoteRealmDictValue | None = None
    if remote_realm is not None:
        do_increment_logging_stat(
            remote_realm,
            COUNT_STATS["mobile_pushes_forwarded::day"],
            None,
            timezone_now(),
            increment=android_successfully_delivered + apple_successfully_delivered,
        )
        remote_realm_dict = {
            "can_push": push_status.can_push,
            "expected_end_timestamp": push_status.expected_end_timestamp,
        }

    deleted_devices = get_deleted_devices(
        user_identity,
        server,
        android_devices=payload.android_devices,
        apple_devices=payload.apple_devices,
    )

    return json_success(
        request,
        data={
            "total_android_devices": len(android_devices),
            "total_apple_devices": len(apple_devices),
            "deleted_devices": deleted_devices,
            "realm": remote_realm_dict,
        },
    )


class DevicesToCleanUpDict(TypedDict):
    android_devices: list[str]
    apple_devices: list[str]


def get_deleted_devices(
    user_identity: UserPushIdentityCompat,
    server: RemoteZulipServer,
    android_devices: list[str],
    apple_devices: list[str],
) -> DevicesToCleanUpDict:
    """The remote server sends us a list of (tokens of) devices that it
    believes it has registered. However some of them may have been
    deleted by us due to errors received in the low level code
    responsible for directly sending push notifications.

    Query the database for the RemotePushDeviceTokens from these lists
    that we do indeed have and return a list of the ones that we don't
    have and thus presumably have already deleted - the remote server
    will want to delete them too.
    """

    android_devices_we_have = RemotePushDeviceToken.objects.filter(
        user_identity.filter_q(),
        token__in=android_devices,
        kind=RemotePushDeviceToken.FCM,
        server=server,
    ).values_list("token", flat=True)
    apple_devices_we_have = RemotePushDeviceToken.objects.filter(
        user_identity.filter_q(),
        token__in=apple_devices,
        kind=RemotePushDeviceToken.APNS,
        server=server,
    ).values_list("token", flat=True)

    return DevicesToCleanUpDict(
        android_devices=list(set(android_devices) - set(android_devices_we_have)),
        apple_devices=list(set(apple_devices) - set(apple_devices_we_have)),
    )


def validate_incoming_table_data(
    server: RemoteZulipServer,
    model: Any,
    rows: list[dict[str, Any]],
    *,
    is_count_stat: bool,
) -> None:
    last_id = get_last_id_from_server(server, model)
    for row in rows:
        # We are silent about stats not in COUNT_STATS which are
        # in LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER --
        # these are stats we stopped recording, but old versions
        # may still have and report.
        if (
            is_count_stat
            and (
                row["property"] not in COUNT_STATS
                or row["property"] in BOUNCER_ONLY_REMOTE_COUNT_STAT_PROPERTIES
            )
            and row["property"] not in LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER
        ):
            raise JsonableError(_("Invalid property {property}").format(property=row["property"]))

        if not is_count_stat and row["event_type"] not in RemoteRealmAuditLog.SYNCED_BILLING_EVENTS:
            raise JsonableError(_("Invalid event type."))

        if row.get("id") is None:
            # This shouldn't be possible, as submitting data like this should be
            # prevented by our param validators.
            raise AssertionError(f"Missing id field in row {row}")
        if row["id"] <= last_id:
            raise JsonableError(_("Data is out of order."))
        last_id = row["id"]


ModelT = TypeVar("ModelT", bound=Model)


def batch_create_table_data(
    server: RemoteZulipServer,
    model: type[ModelT],
    row_objects: list[ModelT],
) -> None:
    # We ignore previously-existing data, in case it was truncated and
    # re-created on the remote server.  Because the existing
    # `bulk_create(..., ignore_conflicts=True)` cannot yet return the
    # ids, or count thereof, of the new inserts, (see
    # https://code.djangoproject.com/ticket/30138), we reach in and
    # call _insert with `returning_fields` in batches ourselves.
    inserted_count = 0
    expected_count = len(row_objects)
    fields = [f for f in model._meta.fields if f.concrete and not f.generated and f.name != "id"]
    while row_objects:
        to_insert, row_objects = row_objects[:1000], row_objects[1000:]
        result = model._default_manager._insert(  # type:ignore[attr-defined]  # This is a private method
            to_insert,
            fields=fields,
            returning_fields=[model._meta.get_field("id")],
            on_conflict=OnConflict.IGNORE,
        )
        inserted_count += len(result)
    if inserted_count < expected_count:
        logging.warning(
            "Dropped %d duplicated rows while saving %d rows of %s for server %s/%s",
            expected_count - inserted_count,
            expected_count,
            model._meta.db_table,
            server.hostname,
            server.uuid,
        )


def ensure_devices_set_remote_realm(
    android_devices: list[RemotePushDeviceToken],
    apple_devices: list[RemotePushDeviceToken],
    remote_realm: RemoteRealm,
) -> None:
    devices_to_update = []
    for device in android_devices + apple_devices:
        if device.remote_realm_id is None:
            device.remote_realm = remote_realm
            devices_to_update.append(device)

    RemotePushDeviceToken.objects.bulk_update(devices_to_update, ["remote_realm"])


def update_remote_realm_data_for_server(
    server: RemoteZulipServer, server_realms_info: list[RealmDataForAnalytics]
) -> None:
    from corporate.lib.stripe import BILLING_SUPPORT_EMAIL, RemoteRealmBillingSession

    reported_uuids = [realm.uuid for realm in server_realms_info]
    all_registered_remote_realms_for_server = list(RemoteRealm.objects.filter(server=server))
    already_registered_remote_realms = [
        remote_realm
        for remote_realm in all_registered_remote_realms_for_server
        if remote_realm.uuid in reported_uuids
    ]
    # RemoteRealm registrations that we have for this server, but aren't
    # present in the data sent to us. We assume this to mean the server
    # must have deleted those realms from the database.
    remote_realms_missing_from_server_data = [
        remote_realm
        for remote_realm in all_registered_remote_realms_for_server
        if remote_realm.uuid not in reported_uuids
    ]

    already_registered_uuids = {
        remote_realm.uuid for remote_realm in already_registered_remote_realms
    }

    new_remote_realms = [
        RemoteRealm(
            server=server,
            uuid=realm.uuid,
            uuid_owner_secret=realm.uuid_owner_secret,
            host=realm.host,
            realm_deactivated=realm.deactivated,
            realm_date_created=timestamp_to_datetime(realm.date_created),
            org_type=realm.org_type,
            name=realm.name,
            authentication_methods=realm.authentication_methods,
            is_system_bot_realm=realm.is_system_bot_realm,
        )
        for realm in server_realms_info
        if realm.uuid not in already_registered_uuids
    ]

    try:
        RemoteRealm.objects.bulk_create(new_remote_realms)
    except IntegrityError as e:
        logger.info(
            "update_remote_realm_data_for_server:server:%s:IntegrityError creating RemoteRealm rows: %s",
            server.id,
            e,
        )
        raise JsonableError(_("Duplicate registration detected."))

    uuid_to_realm_dict = {str(realm.uuid): realm for realm in server_realms_info}
    remote_realms_to_update = []
    remote_realm_audit_logs = []
    now = timezone_now()

    # Update RemoteRealm entries, for which the corresponding realm's info has changed
    # (for the attributes that make sense to sync like this).
    for remote_realm in already_registered_remote_realms:
        modified = False
        realm = uuid_to_realm_dict[str(remote_realm.uuid)]
        for remote_realm_attr, realm_dict_key in [
            ("host", "host"),
            ("org_type", "org_type"),
            ("name", "name"),
            ("authentication_methods", "authentication_methods"),
            ("realm_deactivated", "deactivated"),
            ("is_system_bot_realm", "is_system_bot_realm"),
        ]:
            old_value = getattr(remote_realm, remote_realm_attr)
            new_value = getattr(realm, realm_dict_key)

            if old_value == new_value:
                continue

            setattr(remote_realm, remote_realm_attr, new_value)
            remote_realm_audit_logs.append(
                RemoteRealmAuditLog(
                    server=server,
                    remote_id=None,
                    remote_realm=remote_realm,
                    realm_id=realm.id,
                    event_type=AuditLogEventType.REMOTE_REALM_VALUE_UPDATED,
                    event_time=now,
                    extra_data={
                        "attr_name": remote_realm_attr,
                        "old_value": old_value,
                        "new_value": new_value,
                    },
                )
            )
            modified = True

        if remote_realm.realm_locally_deleted and remote_realm.uuid in reported_uuids:
            remote_realm.realm_locally_deleted = False
            remote_realm_audit_logs.append(
                RemoteRealmAuditLog(
                    server=server,
                    remote_id=None,
                    remote_realm=remote_realm,
                    realm_id=uuid_to_realm_dict[str(remote_realm.uuid)].id,
                    event_type=AuditLogEventType.REMOTE_REALM_LOCALLY_DELETED_RESTORED,
                    event_time=now,
                )
            )
            modified = True

        if modified:
            remote_realms_to_update.append(remote_realm)

    RemoteRealm.objects.bulk_update(
        remote_realms_to_update,
        [
            "host",
            "realm_deactivated",
            "name",
            "authentication_methods",
            "org_type",
            "is_system_bot_realm",
            "realm_locally_deleted",
        ],
    )
    RemoteRealmAuditLog.objects.bulk_create(remote_realm_audit_logs)

    remote_realms_to_update = []
    remote_realm_audit_logs = []
    new_locally_deleted_remote_realms_on_paid_plan_contexts = []
    for remote_realm in remote_realms_missing_from_server_data:
        if not remote_realm.realm_locally_deleted:
            # Otherwise we already knew about this, so nothing to do.
            remote_realm.realm_locally_deleted = True

            ## Temporarily disabled deactivating the registration for
            ## locally deleted realms pending further work on how to
            ## handle test upgrades to 8.0.
            # remote_realm.registration_deactivated = True
            remote_realm_audit_logs.append(
                RemoteRealmAuditLog(
                    server=server,
                    remote_id=None,
                    remote_realm=remote_realm,
                    realm_id=None,
                    event_type=AuditLogEventType.REMOTE_REALM_LOCALLY_DELETED,
                    event_time=now,
                )
            )
            remote_realms_to_update.append(remote_realm)

            billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)
            if (
                billing_session.on_paid_plan()
                and not RemoteRealmAuditLog.objects.filter(
                    server=server,
                    remote_realm=remote_realm,
                    event_type=AuditLogEventType.REMOTE_REALM_LOCALLY_DELETED,
                    event_time__gte=timezone_now() - timedelta(days=1),
                ).exists()
            ):
                context = {
                    "billing_entity": billing_session.billing_entity_display_name,
                    "support_url": billing_session.support_url(),
                    "notice_reason": "locally_deleted_realm_on_paid_plan",
                }
                new_locally_deleted_remote_realms_on_paid_plan_contexts.append(context)

    RemoteRealm.objects.bulk_update(
        remote_realms_to_update,
        ["realm_locally_deleted"],
    )
    RemoteRealmAuditLog.objects.bulk_create(remote_realm_audit_logs)

    email_dict: dict[str, Any] = {
        "template_prefix": "zerver/emails/internal_billing_notice",
        "to_emails": [BILLING_SUPPORT_EMAIL],
        "from_address": FromAddress.tokenized_no_reply_address(),
        "date": timezone_now().strftime(EMAIL_DATE_FORMAT),
    }
    for context in new_locally_deleted_remote_realms_on_paid_plan_contexts:
        email_dict["context"] = context
        queue_event_on_commit("email_senders", email_dict)


def get_human_user_realm_uuids(
    server: RemoteZulipServer,
) -> list[UUID]:
    query = RemoteRealm.objects.filter(
        server=server,
        realm_deactivated=False,
        realm_locally_deleted=False,
        registration_deactivated=False,
        is_system_bot_realm=False,
    ).exclude(
        host__startswith="zulipinternal.",
    )
    if settings.DEVELOPMENT:  # nocoverage
        query = query.exclude(host__startswith="analytics.")

    billable_realm_uuids = list(query.values_list("uuid", flat=True))

    return billable_realm_uuids


@transaction.atomic(durable=True)
def handle_customer_migration_from_server_to_realm(
    server: RemoteZulipServer,
) -> None:
    from corporate.lib.stripe import RemoteRealmBillingSession, RemoteServerBillingSession

    server_billing_session = RemoteServerBillingSession(server)
    server_customer = server_billing_session.get_customer()
    if server_customer is None:
        return

    if server_customer.sponsorship_pending:
        # If we have a pending sponsorship request, defer moving any
        # data until the sponsorship request has been processed. This
        # avoids a race where a sponsorship request made at the server
        # level gets approved after the active plan has already been
        # moved to the sole human RemoteRealm, which would violate
        # invariants.
        return

    server_plan = get_current_plan_by_customer(server_customer)
    if server_plan is None:
        # If the server has no current plan, either because it never
        # had one or because a previous active plan was migrated to
        # the RemoteRealm object, there's nothing to potentially
        # migrate.
        return

    realm_uuids = get_human_user_realm_uuids(server)
    if not realm_uuids:
        return

    event_time = timezone_now()

    if len(realm_uuids) != 1:
        return

    # Here, we have exactly one non-system-bot realm, and some
    # sort of plan on the server; move it to the realm.
    remote_realm = RemoteRealm.objects.get(uuid=realm_uuids[0], server=server)
    remote_realm_customer = get_customer_by_remote_realm(remote_realm)

    # Migrate customer from server to remote realm if there is only one realm.
    if remote_realm_customer is None:
        # In this case the migration is easy, since we can just move the customer
        # object directly.
        server_customer.remote_realm = remote_realm
        server_customer.remote_server = None
        server_customer.save(update_fields=["remote_realm", "remote_server"])
    else:
        # If there's a Customer object for the realm already, things are harder,
        # because it's an unusual state and there may be a plan already active
        # for the realm, or there may have been.
        # In the simplest case, where the realm doesn't have an active plan and the
        # server's plan state can easily be moved, we proceed with the migrations.
        remote_realm_plan = get_current_plan_by_customer(remote_realm_customer)
        if (
            remote_realm_plan is None
            and server_plan.status != CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
            and remote_realm_customer.stripe_customer_id is None
        ):
            # This is a simple case where we don't have to worry about the realm
            # having an active plan or an already configured stripe_customer_id,
            # or the server having a next plan scheduled that we'd need
            # to figure out how to migrate correctly as well.
            # Any other case is too complex to handle here, and should be handled manually,
            # especially since that should be extremely rare.
            server_plan.customer = remote_realm_customer
            server_plan.save(update_fields=["customer"])

            # The realm's customer does not have .stripe_customer_id set by assumption.
            # This situation happens e.g. if the Customer was created by a sponsorship request,
            # so we need to move the value over from the server.
            # That's because the plan we're transferring might be paid or a free trial and
            # therefore need a stripe_customer_id to generate invoices.
            # Hypothetically if the server's customer didn't have a stripe_customer_id set,
            # that would imply the plan doesn't require it (e.g. this might be a Community plan)
            # so we don't have to worry about whether we're copying over a valid value or None here.
            stripe_customer_id = server_customer.stripe_customer_id
            server_customer.stripe_customer_id = None
            server_customer.save(update_fields=["stripe_customer_id"])

            remote_realm_customer.stripe_customer_id = stripe_customer_id
            remote_realm_customer.save(update_fields=["stripe_customer_id"])
        else:
            logger.warning(
                "Failed to migrate customer from server (id: %s) to realm (id: %s): RemoteRealm customer already exists "
                "and plans can't be migrated automatically.",
                server.id,
                remote_realm.id,
            )
            raise JsonableError(
                _(
                    "Couldn't reconcile billing data between server and realm. Please contact {support_email}"
                ).format(support_email=FromAddress.SUPPORT)
            )

    # We successfully moved the plan from the remote server to the remote realm.
    # Update the license ledger for paid plans with automated license management.
    remote_realm_customer = get_customer_by_remote_realm(remote_realm)
    assert remote_realm_customer is not None
    moved_customer_plan = get_current_plan_by_customer(remote_realm_customer)
    assert moved_customer_plan is not None
    if moved_customer_plan.is_a_paid_plan() and moved_customer_plan.automanage_licenses:
        remote_realm_billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)
        try:
            remote_realm_billing_session.update_license_ledger_for_automanaged_plan(
                moved_customer_plan, event_time
            )
        except MissingDataError:  # nocoverage
            logger.warning(
                "Failed to migrate customer from server (id: %s) to realm (id: %s): RemoteZulipServer has stale "
                "audit log data and cannot update license ledger for plan with automated license management.",
                server.id,
                remote_realm.id,
            )
            raise JsonableError(
                _(
                    "Couldn't reconcile billing data between server and realm. Please contact {support_email}"
                ).format(support_email=FromAddress.SUPPORT)
            )

    # TODO: Might be better to call do_change_plan_type here.
    remote_realm.plan_type = server.plan_type
    remote_realm.save(update_fields=["plan_type"])
    server.plan_type = RemoteZulipServer.PLAN_TYPE_SELF_MANAGED
    server.save(update_fields=["plan_type"])
    RemoteRealmAuditLog.objects.create(
        server=server,
        remote_realm=remote_realm,
        event_type=AuditLogEventType.REMOTE_PLAN_TRANSFERRED_SERVER_TO_REALM,
        event_time=event_time,
        extra_data={
            "attr_name": "plan_type",
            "old_value": RemoteRealm.PLAN_TYPE_SELF_MANAGED,
            "new_value": remote_realm.plan_type,
        },
    )


@typed_endpoint
@transaction.atomic(durable=True)
def remote_server_post_analytics(
    request: HttpRequest,
    server: RemoteZulipServer,
    *,
    realm_counts: Json[list[RealmCountDataForAnalytics]],
    installation_counts: Json[list[InstallationCountDataForAnalytics]],
    realmauditlog_rows: Json[list[RealmAuditLogDataForAnalytics]] | None = None,
    realms: Json[list[RealmDataForAnalytics]] | None = None,
    version: Json[str] | None = None,
    merge_base: Json[str] | None = None,
    api_feature_level: Json[int] | None = None,
) -> HttpResponse:
    from corporate.lib.stripe import (
        RemoteRealmBillingSession,
        RemoteServerBillingSession,
        get_push_status_for_remote_request,
    )

    # Lock the server, preventing this from racing with other
    # duplicate submissions of the data
    server = RemoteZulipServer.objects.select_for_update().get(id=server.id)

    remote_server_version_updated = False
    if version is not None:
        version = version[0 : RemoteZulipServer.VERSION_MAX_LENGTH]
    if (
        version != server.last_version
        or merge_base != server.last_merge_base
        or api_feature_level != server.last_api_feature_level
    ):
        server.last_version = version
        server.last_merge_base = merge_base
        server.last_api_feature_level = api_feature_level
        server.save(update_fields=["last_version", "last_merge_base", "last_api_feature_level"])
        remote_server_version_updated = True

    validate_incoming_table_data(
        server,
        RemoteRealmCount,
        [dict(count) for count in realm_counts],
        is_count_stat=True,
    )
    validate_incoming_table_data(
        server,
        RemoteInstallationCount,
        [dict(count) for count in installation_counts],
        is_count_stat=True,
    )

    if realmauditlog_rows is not None:
        validate_incoming_table_data(
            server,
            RemoteRealmAuditLog,
            [dict(row) for row in realmauditlog_rows],
            is_count_stat=False,
        )

    if realms is not None:
        update_remote_realm_data_for_server(server, realms)
        if remote_server_version_updated:
            fix_remote_realm_foreign_keys(server, realms)

    realm_id_to_remote_realm = build_realm_id_to_remote_realm_dict(server, realms)

    # Note that due to skipping rows from the remote server which
    # match LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER, we may
    # theoretically choose to omit the last RemoteRealmCount (or
    # InstallationCount, below) row sent by the remote server, causing
    # them to attempt to re-send that row repeatedlly.  Since the last
    # CountStat is not currently a skipped type, this is, in practice,
    # unlikely to occur.
    #
    # TODO: Record the high-water RealmCount and InstallationCount's
    # `remote_id` values on the RemoteServer, rather than computing
    # them via get_last_id_from_server
    remote_realm_counts = [
        RemoteRealmCount(
            remote_realm=realm_id_to_remote_realm.get(row.realm),
            property=row.property,
            realm_id=row.realm,
            remote_id=row.id,
            server=server,
            end_time=datetime.fromtimestamp(row.end_time, tz=timezone.utc),
            subgroup=row.subgroup,
            value=row.value,
        )
        for row in realm_counts
        if row.property not in LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER
    ]
    batch_create_table_data(server, RemoteRealmCount, remote_realm_counts)

    remote_installation_counts = [
        RemoteInstallationCount(
            property=row.property,
            remote_id=row.id,
            server=server,
            end_time=datetime.fromtimestamp(row.end_time, tz=timezone.utc),
            subgroup=row.subgroup,
            value=row.value,
        )
        for row in installation_counts
        if row.property not in LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER
    ]
    batch_create_table_data(server, RemoteInstallationCount, remote_installation_counts)

    if realmauditlog_rows is not None:
        # Creating audit logs, syncing license ledger, and updating
        # 'last_audit_log_update' needs to be an atomic operation.
        # This helps to rely on 'last_audit_log_update' to assume
        # RemoteRealmAuditLog and LicenseLedger are up-to-date.
        with transaction.atomic(savepoint=False):
            # Important: Do not return early if we receive 0 rows; we must
            # updated last_audit_log_update even if there are no new rows,
            # to help identify server whose ability to connect to this
            # endpoint is broken by a networking problem.
            remote_realms_set = set()
            remote_realm_audit_logs = []
            for row in realmauditlog_rows:
                extra_data = {}
                if isinstance(row.extra_data, str):
                    try:
                        extra_data = orjson.loads(row.extra_data)
                    except orjson.JSONDecodeError:
                        raise JsonableError(_("Malformed audit log data"))
                elif row.extra_data is not None:
                    assert isinstance(row.extra_data, dict)
                    extra_data = row.extra_data
                remote_realms_set.add(realm_id_to_remote_realm.get(row.realm))
                remote_realm_audit_logs.append(
                    RemoteRealmAuditLog(
                        remote_realm=realm_id_to_remote_realm.get(row.realm),
                        realm_id=row.realm,
                        remote_id=row.id,
                        server=server,
                        event_time=datetime.fromtimestamp(row.event_time, tz=timezone.utc),
                        backfilled=row.backfilled,
                        extra_data=extra_data,
                        event_type=row.event_type,
                    )
                )
            batch_create_table_data(server, RemoteRealmAuditLog, remote_realm_audit_logs)

            # We need to update 'last_audit_log_update' before calling the
            # 'sync_license_ledger_if_needed' method to avoid 'MissingDataError'
            # due to 'has_stale_audit_log' being True.
            server.last_audit_log_update = timezone_now()
            server.save(update_fields=["last_audit_log_update"])

            # Update LicenseLedger for remote_realm customers using logs in RemoteRealmAuditlog.
            for remote_realm in remote_realms_set:
                if remote_realm:
                    billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)
                    billing_session.sync_license_ledger_if_needed()

            # Update LicenseLedger for remote_server customer using logs in RemoteRealmAuditlog.
            remote_server_billing_session = RemoteServerBillingSession(remote_server=server)
            remote_server_billing_session.sync_license_ledger_if_needed()

    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    can_push_values = set()

    # Return details on exactly the set of remote realm the client told us about.
    remote_realm_dict: dict[str, RemoteRealmDictValue] = {}
    remote_human_realm_count = len(
        [
            remote_realm
            for remote_realm in realm_id_to_remote_realm.values()
            if not remote_realm.is_system_bot_realm
        ]
    )
    for remote_realm in realm_id_to_remote_realm.values():
        uuid = str(remote_realm.uuid)
        status = get_push_status_for_remote_request(server, remote_realm)
        if remote_realm.is_system_bot_realm:
            # Ignore system bot realms for computing log_data
            pass
        elif remote_human_realm_count == 1:  # nocoverage
            log_data["extra"] = f"[can_push={status.can_push}/{status.message}]"
        else:
            can_push_values.add(status.can_push)
        remote_realm_dict[uuid] = {
            "can_push": status.can_push,
            "expected_end_timestamp": status.expected_end_timestamp,
        }

    if len(can_push_values) == 1:
        can_push_value = next(iter(can_push_values))
        log_data["extra"] = f"[can_push={can_push_value}/{remote_human_realm_count} realms]"
    elif can_push_values == {True, False}:
        log_data["extra"] = f"[can_push=mixed/{remote_human_realm_count} realms]"
    elif remote_human_realm_count == 0:
        log_data["extra"] = "[0 realms]"
    return json_success(request, data={"realms": remote_realm_dict})


def build_realm_id_to_remote_realm_dict(
    server: RemoteZulipServer, realms: list[RealmDataForAnalytics] | None
) -> dict[int, RemoteRealm]:
    if realms is None:
        return {}

    realm_uuids = [realm.uuid for realm in realms]
    remote_realms = RemoteRealm.objects.filter(uuid__in=realm_uuids, server=server)

    uuid_to_remote_realm_dict = {
        str(remote_realm.uuid): remote_realm for remote_realm in remote_realms
    }
    return {realm.id: uuid_to_remote_realm_dict[str(realm.uuid)] for realm in realms}


def fix_remote_realm_foreign_keys(
    server: RemoteZulipServer, realms: list[RealmDataForAnalytics]
) -> None:
    """
    Finds the RemoteRealmCount and RemoteRealmAuditLog entries without .remote_realm
    set and sets it based on the "realms" data received from the remote server,
    if possible.
    """

    if (
        not RemoteRealmCount.objects.filter(server=server, remote_realm=None).exists()
        and not RemoteRealmAuditLog.objects.filter(server=server, remote_realm=None).exists()
    ):
        return

    realm_id_to_remote_realm = build_realm_id_to_remote_realm_dict(server, realms)
    for realm_id in realm_id_to_remote_realm:
        RemoteRealmCount.objects.filter(server=server, remote_realm=None, realm_id=realm_id).update(
            remote_realm=realm_id_to_remote_realm[realm_id]
        )
        RemoteRealmAuditLog.objects.filter(
            server=server, remote_realm=None, realm_id=realm_id
        ).update(remote_realm=realm_id_to_remote_realm[realm_id])


def get_last_id_from_server(server: RemoteZulipServer, model: Any) -> int:
    last_count = (
        model.objects.filter(server=server)
        # Rows with remote_id=None are managed by the bouncer service itself,
        # and thus aren't meant for syncing and should be ignored here.
        .exclude(remote_id=None)
        .order_by("remote_id")
        .only("remote_id")
        .last()
    )
    if last_count is not None:
        return last_count.remote_id
    return 0


@typed_endpoint_without_parameters
def remote_server_check_analytics(request: HttpRequest, server: RemoteZulipServer) -> HttpResponse:
    result = {
        "last_realm_count_id": get_last_id_from_server(server, RemoteRealmCount),
        "last_installation_count_id": get_last_id_from_server(server, RemoteInstallationCount),
        "last_realmauditlog_id": get_last_id_from_server(server, RemoteRealmAuditLog),
    }
    return json_success(request, data=result)
