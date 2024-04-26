import logging
import re
from email.headerregistry import Address
from typing import Any, Dict, List, Optional, Tuple

import DNS
from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpRequest
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import get_language, gettext_lazy
from django.utils.translation import gettext as _
from markupsafe import Markup
from two_factor.forms import AuthenticationTokenForm as TwoFactorAuthenticationTokenForm
from two_factor.utils import totp_digits
from typing_extensions import override

from zerver.actions.user_settings import do_change_password
from zerver.lib.email_validation import (
    email_allowed_for_realm,
    email_reserved_for_system_bots_error,
    validate_is_not_disposable,
)
from zerver.lib.exceptions import JsonableError, RateLimitedError
from zerver.lib.i18n import get_language_list
from zerver.lib.name_restrictions import is_reserved_subdomain
from zerver.lib.rate_limiter import RateLimitedObject, rate_limit_request_by_ip
from zerver.lib.send_email import FromAddress, send_email
from zerver.lib.soft_deactivation import queue_soft_reactivation
from zerver.lib.subdomains import get_subdomain, is_root_domain_available
from zerver.lib.users import check_full_name
from zerver.models import Realm, UserProfile
from zerver.models.realm_audit_logs import RealmAuditLog
from zerver.models.realms import (
    DisposableEmailError,
    DomainNotAllowedForRealmError,
    EmailContainsPlusError,
    get_realm,
)
from zerver.models.users import get_user_by_delivery_email, is_cross_realm_bot_email
from zproject.backends import check_password_strength, email_auth_enabled, email_belongs_to_ldap

if settings.BILLING_ENABLED:
    from corporate.lib.registration import check_spare_licenses_available_for_registering_new_user
    from corporate.lib.stripe import LicenseLimitError

# We don't mark this error for translation, because it's displayed
# only to MIT users.
MIT_VALIDATION_ERROR = Markup(
    "That user does not exist at MIT or is a"
    ' <a href="https://ist.mit.edu/email-lists">mailing list</a>.'
    " If you want to sign up an alias for Zulip,"
    ' <a href="mailto:support@zulip.com">contact us</a>.'
)

DEACTIVATED_ACCOUNT_ERROR = gettext_lazy(
    "Your account {username} has been deactivated."
    " Please contact your organization administrator to reactivate it."
)
PASSWORD_TOO_WEAK_ERROR = gettext_lazy("The password is too weak.")


def email_is_not_mit_mailing_list(email: str) -> None:
    """Prevent MIT mailing lists from signing up for Zulip"""
    address = Address(addr_spec=email)
    if address.domain == "mit.edu":
        # Check whether the user exists and can get mail.
        try:
            DNS.dnslookup(f"{address.username}.pobox.ns.athena.mit.edu", DNS.Type.TXT)
        except DNS.Base.ServerError as e:
            if e.rcode == DNS.Status.NXDOMAIN:
                # This error is Markup only because 1. it needs to render HTML
                # 2. It's not formatted with any user input.
                raise ValidationError(MIT_VALIDATION_ERROR)
            else:
                raise AssertionError("Unexpected DNS error")


class OverridableValidationError(ValidationError):
    pass


def check_subdomain_available(subdomain: str, allow_reserved_subdomain: bool = False) -> None:
    error_strings = {
        "too short": _("Subdomain needs to have length 3 or greater."),
        "extremal dash": _("Subdomain cannot start or end with a '-'."),
        "bad character": _("Subdomain can only have lowercase letters, numbers, and '-'s."),
        "unavailable": _("Subdomain already in use. Please choose a different one."),
        "reserved": _("Subdomain reserved. Please choose a different one."),
    }

    if subdomain == Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
        if is_root_domain_available():
            return
        raise ValidationError(error_strings["unavailable"])
    if subdomain[0] == "-" or subdomain[-1] == "-":
        raise ValidationError(error_strings["extremal dash"])
    if not re.match(r"^[a-z0-9-]*$", subdomain):
        raise ValidationError(error_strings["bad character"])
    if len(subdomain) < 3:
        raise ValidationError(error_strings["too short"])
    if Realm.objects.filter(string_id=subdomain).exists():
        raise ValidationError(error_strings["unavailable"])
    if is_reserved_subdomain(subdomain) and not allow_reserved_subdomain:
        raise OverridableValidationError(
            error_strings["reserved"],
            "Pass --allow-reserved-subdomain to override",
        )


def email_not_system_bot(email: str) -> None:
    if is_cross_realm_bot_email(email):
        msg = email_reserved_for_system_bots_error(email)
        code = msg
        raise ValidationError(
            msg,
            code=code,
            params=dict(deactivated=False),
        )


def email_is_not_disposable(email: str) -> None:
    try:
        validate_is_not_disposable(email)
    except DisposableEmailError:
        raise ValidationError(_("Please use your real email address."))


class RealmDetailsForm(forms.Form):
    realm_subdomain = forms.CharField(max_length=Realm.MAX_REALM_SUBDOMAIN_LENGTH, required=False)
    realm_type = forms.TypedChoiceField(
        coerce=int, choices=[(t["id"], t["name"]) for t in Realm.ORG_TYPES.values()]
    )
    realm_default_language = forms.ChoiceField(choices=[])
    realm_name = forms.CharField(max_length=Realm.MAX_REALM_NAME_LENGTH)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Since the superclass doesn't accept random extra kwargs, we
        # remove it from the kwargs dict before initializing.
        self.realm_creation = kwargs["realm_creation"]
        del kwargs["realm_creation"]

        super().__init__(*args, **kwargs)
        self.fields["realm_default_language"] = forms.ChoiceField(
            choices=[(lang["code"], lang["name"]) for lang in get_language_list()],
        )

    def clean_realm_subdomain(self) -> str:
        if not self.realm_creation:
            # This field is only used if realm_creation
            return ""

        subdomain = self.cleaned_data["realm_subdomain"]
        if "realm_in_root_domain" in self.data:
            subdomain = Realm.SUBDOMAIN_FOR_ROOT_DOMAIN

        check_subdomain_available(subdomain)
        return subdomain


class RegistrationForm(RealmDetailsForm):
    MAX_PASSWORD_LENGTH = 100
    full_name = forms.CharField(max_length=UserProfile.MAX_NAME_LENGTH)
    # The required-ness of the password field gets overridden if it isn't
    # actually required for a realm
    password = forms.CharField(widget=forms.PasswordInput, max_length=MAX_PASSWORD_LENGTH)
    is_demo_organization = forms.BooleanField(required=False)
    enable_marketing_emails = forms.BooleanField(required=False)
    email_address_visibility = forms.TypedChoiceField(
        required=False,
        coerce=int,
        empty_value=None,
        choices=list(UserProfile.EMAIL_ADDRESS_VISIBILITY_ID_TO_NAME_MAP.items()),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Since the superclass doesn't except random extra kwargs, we
        # remove it from the kwargs dict before initializing.
        self.realm_creation = kwargs["realm_creation"]
        self.realm = kwargs.pop("realm", None)

        super().__init__(*args, **kwargs)
        if settings.TERMS_OF_SERVICE_VERSION is not None:
            self.fields["terms"] = forms.BooleanField(required=True)
        self.fields["realm_name"] = forms.CharField(
            max_length=Realm.MAX_REALM_NAME_LENGTH, required=self.realm_creation
        )
        self.fields["realm_type"] = forms.TypedChoiceField(
            coerce=int,
            choices=[(t["id"], t["name"]) for t in Realm.ORG_TYPES.values()],
            required=self.realm_creation,
        )
        self.fields["realm_default_language"] = forms.ChoiceField(
            choices=[(lang["code"], lang["name"]) for lang in get_language_list()],
            required=self.realm_creation,
        )
        self.fields["how_realm_creator_found_zulip"] = forms.ChoiceField(
            choices=RealmAuditLog.HOW_REALM_CREATOR_FOUND_ZULIP_OPTIONS.items(),
            required=self.realm_creation,
        )
        self.fields["how_realm_creator_found_zulip_other_text"] = forms.CharField(
            max_length=100, required=False
        )
        self.fields["how_realm_creator_found_zulip_where_ad"] = forms.CharField(
            max_length=100, required=False
        )
        self.fields["how_realm_creator_found_zulip_which_organization"] = forms.CharField(
            max_length=100, required=False
        )

    def clean_full_name(self) -> str:
        try:
            return check_full_name(
                full_name_raw=self.cleaned_data["full_name"], user_profile=None, realm=self.realm
            )
        except JsonableError as e:
            raise ValidationError(e.msg)

    def clean_password(self) -> str:
        password = self.cleaned_data["password"]
        if self.fields["password"].required and not check_password_strength(password):
            # The frontend code tries to stop the user from submitting the form with a weak password,
            # but if the user bypasses that protection, this error code path will run.
            raise ValidationError(str(PASSWORD_TOO_WEAK_ERROR))

        return password


class ToSForm(forms.Form):
    terms = forms.BooleanField(required=False)
    email_address_visibility = forms.TypedChoiceField(
        required=False,
        coerce=int,
        empty_value=None,
        choices=list(UserProfile.EMAIL_ADDRESS_VISIBILITY_ID_TO_NAME_MAP.items()),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if settings.TERMS_OF_SERVICE_VERSION is not None:
            self.fields["terms"] = forms.BooleanField(required=True)


class HomepageForm(forms.Form):
    email = forms.EmailField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.realm = kwargs.pop("realm", None)
        self.from_multiuse_invite = kwargs.pop("from_multiuse_invite", False)
        self.invited_as = kwargs.pop("invited_as", None)
        super().__init__(*args, **kwargs)

    def clean_email(self) -> str:
        """Returns the email if and only if the user's email address is
        allowed to join the realm they are trying to join."""
        email = self.cleaned_data["email"]

        # Otherwise, the user is trying to join a specific realm.
        realm = self.realm
        from_multiuse_invite = self.from_multiuse_invite

        if realm is None:
            raise ValidationError(
                _("The organization you are trying to join using {email} does not exist.").format(
                    email=email
                )
            )

        if not from_multiuse_invite and realm.invite_required:
            raise ValidationError(
                _(
                    "Please request an invite for {email} "
                    "from the organization "
                    "administrator."
                ).format(email=email)
            )

        try:
            email_allowed_for_realm(email, realm)
        except DomainNotAllowedForRealmError:
            raise ValidationError(
                _(
                    "Your email address, {email}, is not in one of the domains "
                    "that are allowed to register for accounts in this organization."
                ).format(email=email)
            )
        except DisposableEmailError:
            raise ValidationError(_("Please use your real email address."))
        except EmailContainsPlusError:
            raise ValidationError(
                _("Email addresses containing + are not allowed in this organization.")
            )

        if realm.is_zephyr_mirror_realm:
            email_is_not_mit_mailing_list(email)

        if settings.BILLING_ENABLED:
            role = self.invited_as if self.invited_as is not None else UserProfile.ROLE_MEMBER
            try:
                check_spare_licenses_available_for_registering_new_user(realm, email, role=role)
            except LicenseLimitError:
                raise ValidationError(
                    _(
                        "New members cannot join this organization because all Zulip licenses are in use. Please contact the person who "
                        "invited you and ask them to increase the number of licenses, then try again."
                    )
                )

        return email


class RealmCreationForm(RealmDetailsForm):
    # This form determines whether users can create a new realm.
    email = forms.EmailField(validators=[email_not_system_bot, email_is_not_disposable])

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["realm_creation"] = True
        super().__init__(*args, **kwargs)


class LoggingSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label=_("New password"),
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
        help_text=password_validation.password_validators_help_text_html(),
        max_length=RegistrationForm.MAX_PASSWORD_LENGTH,
    )
    new_password2 = forms.CharField(
        label=_("New password confirmation"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        max_length=RegistrationForm.MAX_PASSWORD_LENGTH,
    )

    def clean_new_password1(self) -> str:
        new_password = self.cleaned_data["new_password1"]
        if not check_password_strength(new_password):
            # The frontend code tries to stop the user from submitting the form with a weak password,
            # but if the user bypasses that protection, this error code path will run.
            raise ValidationError(str(PASSWORD_TOO_WEAK_ERROR))

        return new_password

    @override
    def save(self, commit: bool = True) -> UserProfile:
        assert isinstance(self.user, UserProfile)
        do_change_password(self.user, self.cleaned_data["new_password1"], commit=commit)
        return self.user


def generate_password_reset_url(
    user_profile: UserProfile, token_generator: PasswordResetTokenGenerator
) -> str:
    token = token_generator.make_token(user_profile)
    uid = urlsafe_base64_encode(str(user_profile.id).encode())
    endpoint = reverse("password_reset_confirm", kwargs=dict(uidb64=uid, token=token))
    return f"{user_profile.realm.uri}{endpoint}"


class ZulipPasswordResetForm(PasswordResetForm):
    @override
    def save(
        self,
        domain_override: Optional[str] = None,
        subject_template_name: str = "registration/password_reset_subject.txt",
        email_template_name: str = "registration/password_reset_email.html",
        use_https: bool = False,
        token_generator: PasswordResetTokenGenerator = default_token_generator,
        from_email: Optional[str] = None,
        request: Optional[HttpRequest] = None,
        html_email_template_name: Optional[str] = None,
        extra_email_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        If the email address has an account in the target realm,
        generates a one-use only link for resetting password and sends
        to the user.

        We send a different email if an associated account does not exist in the
        database, or an account does exist, but not in the realm.

        Note: We ignore protocol and the various email template arguments (those
        are an artifact of using Django's password reset framework).
        """
        email = self.cleaned_data["email"]
        # The form is only used in zerver.views.auth.password_rest, we know that
        # the request must not be None
        assert request is not None

        realm = get_realm(get_subdomain(request))

        if not email_auth_enabled(realm):
            logging.info(
                "Password reset attempted for %s even though password auth is disabled.", email
            )
            return
        if email_belongs_to_ldap(realm, email):
            # TODO: Ideally, we'd provide a user-facing error here
            # about the fact that they aren't allowed to have a
            # password in the Zulip server and should change it in LDAP.
            logging.info("Password reset not allowed for user in LDAP domain")
            return
        if realm.deactivated:
            logging.info("Realm is deactivated")
            return

        if settings.RATE_LIMITING:
            try:
                rate_limit_password_reset_form_by_email(email)
                rate_limit_request_by_ip(request, domain="sends_email_by_ip")
            except RateLimitedError:
                logging.info(
                    "Too many password reset attempts for email %s from %s",
                    email,
                    request.META["REMOTE_ADDR"],
                )
                # The view will handle the RateLimit exception and render an appropriate page
                raise

        try:
            user = get_user_by_delivery_email(email, realm)
        except UserProfile.DoesNotExist:
            user = None

        context = {
            "email": email,
            "realm_uri": realm.uri,
            "realm_name": realm.name,
        }

        if user is not None and not user.is_active:
            context["user_deactivated"] = True
            user = None

        if user is not None:
            context["active_account_in_realm"] = True
            context["reset_url"] = generate_password_reset_url(user, token_generator)
            queue_soft_reactivation(user.id)
            send_email(
                "zerver/emails/password_reset",
                to_user_ids=[user.id],
                from_name=FromAddress.security_email_from_name(user_profile=user),
                from_address=FromAddress.tokenized_no_reply_address(),
                context=context,
                realm=realm,
                request=request,
            )
        else:
            context["active_account_in_realm"] = False
            active_accounts_in_other_realms = UserProfile.objects.filter(
                delivery_email__iexact=email, is_active=True
            )
            if active_accounts_in_other_realms:
                context["active_accounts_in_other_realms"] = active_accounts_in_other_realms
            language = get_language()

            send_email(
                "zerver/emails/password_reset",
                to_emails=[email],
                from_name=FromAddress.security_email_from_name(language=language),
                from_address=FromAddress.tokenized_no_reply_address(),
                language=language,
                context=context,
                realm=realm,
                request=request,
            )


class RateLimitedPasswordResetByEmail(RateLimitedObject):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__()

    @override
    def key(self) -> str:
        return f"{type(self).__name__}:{self.email}"

    @override
    def rules(self) -> List[Tuple[int, int]]:
        return settings.RATE_LIMITING_RULES["password_reset_form_by_email"]


def rate_limit_password_reset_form_by_email(email: str) -> None:
    ratelimited, secs_to_freedom = RateLimitedPasswordResetByEmail(email).rate_limit()
    if ratelimited:
        raise RateLimitedError(secs_to_freedom)


class CreateUserForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    email = forms.EmailField()


class OurAuthenticationForm(AuthenticationForm):
    logger = logging.getLogger("zulip.auth.OurAuthenticationForm")

    @override
    def clean(self) -> Dict[str, Any]:
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            assert self.request is not None
            subdomain = get_subdomain(self.request)
            realm = get_realm(subdomain)

            return_data: Dict[str, Any] = {}
            try:
                self.user_cache = authenticate(
                    request=self.request,
                    username=username,
                    password=password,
                    realm=realm,
                    return_data=return_data,
                )
            except RateLimitedError as e:
                assert e.secs_to_freedom is not None
                secs_to_freedom = int(e.secs_to_freedom)
                error_message = _(
                    "You're making too many attempts to sign in."
                    " Try again in {seconds} seconds or contact your organization administrator"
                    " for help."
                )
                raise ValidationError(error_message.format(seconds=secs_to_freedom))

            if return_data.get("inactive_realm"):
                raise AssertionError("Programming error: inactive realm in authentication form")

            if return_data.get("password_reset_needed"):
                raise ValidationError(
                    _(
                        "Your password has been disabled because it is too weak. "
                        "Reset your password to create a new one."
                    )
                )

            if return_data.get("inactive_user") and not return_data.get("is_mirror_dummy"):
                # We exclude mirror dummy accounts here. They should be treated as the
                # user never having had an account, so we let them fall through to the
                # normal invalid_login case below.
                error_message = DEACTIVATED_ACCOUNT_ERROR.format(username=username)
                raise ValidationError(error_message)

            if return_data.get("invalid_subdomain"):
                self.logger.info(
                    "User attempted password login to wrong subdomain %s. Matching accounts: %s",
                    subdomain,
                    return_data.get("matching_user_ids_in_different_realms"),
                )
                # We don't want to leak information by revealing there are matching accounts
                # on different subdomain - so we just fall through to the default error.
                assert self.user_cache is None

            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages["invalid_login"],
                    code="invalid_login",
                    params={"username": self.username_field.verbose_name},
                )

            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    @override
    def add_prefix(self, field_name: str) -> str:
        """Disable prefix, since Zulip doesn't use this Django forms feature
        (and django-two-factor does use it), and we'd like both to be
        happy with this form.
        """
        return field_name


class AuthenticationTokenForm(TwoFactorAuthenticationTokenForm):
    """
    We add this form to update the widget of otp_token. The default
    widget is an input element whose type is a number, which doesn't
    stylistically match our theme.
    """

    otp_token = forms.IntegerField(
        label=_("Token"), min_value=1, max_value=int("9" * totp_digits()), widget=forms.TextInput
    )


class MultiEmailField(forms.Field):
    @override
    def to_python(self, emails: Optional[str]) -> List[str]:
        """Normalize data to a list of strings."""
        if not emails:
            return []

        return [email.strip() for email in emails.split(",")]

    @override
    def validate(self, emails: List[str]) -> None:
        """Check if value consists only of valid emails."""
        super().validate(emails)
        for email in emails:
            validate_email(email)


class FindMyTeamForm(forms.Form):
    emails = MultiEmailField(
        help_text=_("Tip: You can enter multiple email addresses with commas between them.")
    )

    def clean_emails(self) -> List[str]:
        emails = self.cleaned_data["emails"]
        if len(emails) > 10:
            raise forms.ValidationError(_("Please enter at most 10 emails."))

        return emails


class RealmRedirectForm(forms.Form):
    subdomain = forms.CharField(max_length=Realm.MAX_REALM_SUBDOMAIN_LENGTH, required=True)

    def clean_subdomain(self) -> str:
        subdomain = self.cleaned_data["subdomain"]
        try:
            get_realm(subdomain)
        except Realm.DoesNotExist:
            raise ValidationError(_("We couldn't find that Zulip organization."))
        return subdomain
