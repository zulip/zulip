
from django import forms
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.forms import SetPasswordForm, AuthenticationForm, \
    PasswordResetForm
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.core.validators import validate_email
from django.db.models.query import QuerySet
from django.utils.translation import ugettext as _
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.http import HttpRequest
from jinja2 import Markup as mark_safe

from zerver.lib.actions import do_change_password, user_email_is_unique, \
    validate_email_for_realm
from zerver.lib.name_restrictions import is_reserved_subdomain, is_disposable_domain
from zerver.lib.request import JsonableError
from zerver.lib.send_email import send_email, FromAddress
from zerver.lib.subdomains import get_subdomain, user_matches_subdomain, is_root_domain_available
from zerver.lib.users import check_full_name
from zerver.models import Realm, get_user_profile_by_email, UserProfile, \
    get_realm, email_to_domain, email_allowed_for_realm
from zproject.backends import email_auth_enabled

import logging
import re
import DNS

from typing import Any, Callable, List, Optional, Text, Dict

MIT_VALIDATION_ERROR = u'That user does not exist at MIT or is a ' + \
                       u'<a href="https://ist.mit.edu/email-lists">mailing list</a>. ' + \
                       u'If you want to sign up an alias for Zulip, ' + \
                       u'<a href="mailto:support@zulipchat.com">contact us</a>.'
WRONG_SUBDOMAIN_ERROR = "Your Zulip account is not a member of the " + \
                        "organization associated with this subdomain.  " + \
                        "Please contact %s with any questions!" % (FromAddress.SUPPORT,)

def email_is_not_mit_mailing_list(email):
    # type: (Text) -> None
    """Prevent MIT mailing lists from signing up for Zulip"""
    if "@mit.edu" in email:
        username = email.rsplit("@", 1)[0]
        # Check whether the user exists and can get mail.
        try:
            DNS.dnslookup("%s.pobox.ns.athena.mit.edu" % username, DNS.Type.TXT)
        except DNS.Base.ServerError as e:
            if e.rcode == DNS.Status.NXDOMAIN:
                raise ValidationError(mark_safe(MIT_VALIDATION_ERROR))
            else:
                raise AssertionError("Unexpected DNS error")

def check_subdomain_available(subdomain):
    # type: (str) -> None
    error_strings = {
        'too short': _("Subdomain needs to have length 3 or greater."),
        'extremal dash': _("Subdomain cannot start or end with a '-'."),
        'bad character': _("Subdomain can only have lowercase letters, numbers, and '-'s."),
        'unavailable': _("Subdomain unavailable. Please choose a different one.")}

    if subdomain == Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
        if is_root_domain_available():
            return
        raise ValidationError(error_strings['unavailable'])
    if len(subdomain) < 3:
        raise ValidationError(error_strings['too short'])
    if subdomain[0] == '-' or subdomain[-1] == '-':
        raise ValidationError(error_strings['extremal dash'])
    if not re.match('^[a-z0-9-]*$', subdomain):
        raise ValidationError(error_strings['bad character'])
    if is_reserved_subdomain(subdomain) or \
       get_realm(subdomain) is not None:
        raise ValidationError(error_strings['unavailable'])

class RegistrationForm(forms.Form):
    MAX_PASSWORD_LENGTH = 100
    full_name = forms.CharField(max_length=UserProfile.MAX_NAME_LENGTH)
    # The required-ness of the password field gets overridden if it isn't
    # actually required for a realm
    password = forms.CharField(widget=forms.PasswordInput, max_length=MAX_PASSWORD_LENGTH)
    realm_subdomain = forms.CharField(max_length=Realm.MAX_REALM_SUBDOMAIN_LENGTH, required=False)

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None

        # Since the superclass doesn't except random extra kwargs, we
        # remove it from the kwargs dict before initializing.
        self.realm_creation = kwargs['realm_creation']
        del kwargs['realm_creation']

        super().__init__(*args, **kwargs)
        if settings.TERMS_OF_SERVICE:
            self.fields['terms'] = forms.BooleanField(required=True)
        self.fields['realm_name'] = forms.CharField(
            max_length=Realm.MAX_REALM_NAME_LENGTH,
            required=self.realm_creation)

    def clean_full_name(self):
        # type: () -> Text
        try:
            return check_full_name(self.cleaned_data['full_name'])
        except JsonableError as e:
            raise ValidationError(e.msg)

    def clean_realm_subdomain(self):
        # type: () -> str
        if not self.realm_creation:
            # This field is only used if realm_creation
            return ""

        subdomain = self.cleaned_data['realm_subdomain']
        if 'realm_in_root_domain' in self.data:
            subdomain = Realm.SUBDOMAIN_FOR_ROOT_DOMAIN

        check_subdomain_available(subdomain)
        return subdomain

class ToSForm(forms.Form):
    terms = forms.BooleanField(required=True)

class HomepageForm(forms.Form):
    email = forms.EmailField()

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        self.realm = kwargs.pop('realm', None)
        self.from_multiuse_invite = kwargs.pop('from_multiuse_invite', False)
        super().__init__(*args, **kwargs)

    def clean_email(self):
        # type: () -> str
        """Returns the email if and only if the user's email address is
        allowed to join the realm they are trying to join."""
        email = self.cleaned_data['email']

        # Otherwise, the user is trying to join a specific realm.
        realm = self.realm
        from_multiuse_invite = self.from_multiuse_invite

        if realm is None:
            raise ValidationError(_("The organization you are trying to "
                                    "join using {email} does not "
                                    "exist.").format(email=email))

        if not from_multiuse_invite and realm.invite_required:
            raise ValidationError(_("Please request an invite for {email} "
                                    "from the organization "
                                    "administrator.").format(email=email))

        if not email_allowed_for_realm(email, realm):
            raise ValidationError(
                _("Your email address, {email}, is not in one of the domains "
                  "that are allowed to register for accounts in this organization.").format(
                      string_id=realm.string_id, email=email))

        validate_email_for_realm(realm, email)

        if realm.is_zephyr_mirror_realm:
            email_is_not_mit_mailing_list(email)

        return email

def email_is_not_disposable(email):
    # type: (Text) -> None
    if is_disposable_domain(email_to_domain(email)):
        raise ValidationError(_("Please use your real email address."))

class RealmCreationForm(forms.Form):
    # This form determines whether users can create a new realm.
    email = forms.EmailField(validators=[user_email_is_unique, email_is_not_disposable])

class LoggingSetPasswordForm(SetPasswordForm):
    def save(self, commit=True):
        # type: (bool) -> UserProfile
        do_change_password(self.user, self.cleaned_data['new_password1'],
                           commit=commit)
        return self.user

class ZulipPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        # type: (str) -> QuerySet
        """Given an email, return matching user(s) who should receive a reset.

        This is modified from the original in that it allows non-bot
        users who don't have a usable password to reset their
        passwords.
        """
        if not email_auth_enabled():
            logging.info("Password reset attempted for %s even though password auth is disabled." % (email,))
            return []
        result = UserProfile.objects.filter(email__iexact=email, is_active=True,
                                            is_bot=False)
        if len(result) == 0:
            logging.info("Password reset attempted for %s; no active account." % (email,))
        return result

    def send_mail(self, context, from_email, to_email):
        # type: (Dict[str, Any], str, str) -> None
        """
        Currently we don't support accounts in multiple subdomains using
        a single email address. We override this function so that we do
        not send a reset link to an email address if the reset attempt is
        done on the subdomain which does not match user.realm.subdomain.

        Once we start supporting accounts with the same email in
        multiple subdomains, we may be able to refactor this function.

        A second reason we override this function is so that we can send
        the mail through the functions in zerver.lib.send_email, to match
        how we send all other mail in the codebase.
        """
        user = get_user_profile_by_email(to_email)
        attempted_subdomain = get_subdomain(self.request)
        context['attempted_realm'] = False
        if not user_matches_subdomain(attempted_subdomain, user):
            context['attempted_realm'] = get_realm(attempted_subdomain)

        send_email('zerver/emails/password_reset', to_user_id=user.id,
                   from_name="Zulip Account Security",
                   from_address=FromAddress.NOREPLY, context=context)

    def save(self,
             subject_template_name='registration/password_reset_subject.txt',  # type: Text
             email_template_name='registration/password_reset_email.html',  # type: Text
             use_https=False,  # type: bool
             token_generator=default_token_generator,  # type: PasswordResetTokenGenerator
             from_email=None,  # type: Optional[Text]
             request=None,  # type: HttpRequest
             html_email_template_name=None,  # type: Optional[Text]
             extra_email_context=None  # type: Optional[Dict[str, Any]]
             ):
        # type: (...) -> None
        """
        Currently we don't support accounts in multiple subdomains using a
        single email addresss. Once we start supporting accounts with the same
        email in multiple subdomains, we may be able to delete or refactor this
        function.

        Generates a one-use only link for resetting password and sends to the
        user.

        Note: We ignore the various email template arguments (those
        are an artifact of using Django's password reset framework)

        """
        setattr(self, 'request', request)
        email = self.cleaned_data["email"]
        users = list(self.get_users(email))

        for user in users:
            context = {
                'email': email,
                'uid': urlsafe_base64_encode(force_bytes(user.id)),
                'user': user,
                'token': token_generator.make_token(user),
                'protocol': 'https' if use_https else 'http',
            }
            if extra_email_context is not None:
                context.update(extra_email_context)
            self.send_mail(context, from_email, email)

class CreateUserForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    email = forms.EmailField()

class OurAuthenticationForm(AuthenticationForm):
    def clean_username(self):
        # type: () -> str
        email = self.cleaned_data['username']
        try:
            user_profile = get_user_profile_by_email(email)
        except UserProfile.DoesNotExist:
            return email

        if user_profile.realm.deactivated:
            error_msg = u"""Sorry for the trouble, but %s has been deactivated.

Please contact %s to reactivate this group.""" % (
                user_profile.realm.name,
                FromAddress.SUPPORT)
            raise ValidationError(mark_safe(error_msg))

        if not user_profile.is_active and not user_profile.is_mirror_dummy:
            error_msg = (
                u"Sorry for the trouble, but your account has been deactivated. "
                u"Please contact your organization administrator to reactivate it. "
                u"If you're not sure who that is, try contacting %s.") % (FromAddress.SUPPORT,)
            raise ValidationError(mark_safe(error_msg))

        if not user_matches_subdomain(get_subdomain(self.request), user_profile):
            logging.warning("User %s attempted to password login to wrong subdomain %s" %
                            (user_profile.email, get_subdomain(self.request)))
            raise ValidationError(mark_safe(WRONG_SUBDOMAIN_ERROR))
        return email

    def clean(self):
        # type: () -> Dict[str, Any]
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username is not None and password:
            subdomain = get_subdomain(self.request)
            self.user_cache = authenticate(self.request, username=username, password=password,
                                           realm_subdomain=subdomain)
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                    params={'username': self.username_field.verbose_name},
                )
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

class MultiEmailField(forms.Field):
    def to_python(self, emails):
        # type: (Text) -> List[Text]
        """Normalize data to a list of strings."""
        if not emails:
            return []

        return [email.strip() for email in emails.split(',')]

    def validate(self, emails):
        # type: (List[Text]) -> None
        """Check if value consists only of valid emails."""
        super().validate(emails)
        for email in emails:
            validate_email(email)

class FindMyTeamForm(forms.Form):
    emails = MultiEmailField(
        help_text=_("Add up to 10 comma-separated email addresses."))

    def clean_emails(self):
        # type: () -> List[Text]
        emails = self.cleaned_data['emails']
        if len(emails) > 10:
            raise forms.ValidationError(_("Please enter at most 10 emails."))

        return emails
