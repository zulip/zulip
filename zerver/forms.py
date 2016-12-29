from __future__ import absolute_import

from django import forms
from django.conf import settings
from django.contrib.auth.forms import SetPasswordForm, AuthenticationForm, \
    PasswordResetForm
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db.models.query import QuerySet
from django.utils.translation import ugettext as _
from jinja2 import Markup as mark_safe

from zerver.lib.actions import do_change_password, is_inactive, user_email_is_unique
from zerver.lib.name_restrictions import is_reserved_subdomain, is_disposable_domain
from zerver.lib.utils import get_subdomain, check_subdomain
from zerver.models import Realm, get_user_profile_by_email, UserProfile, \
    get_realm_by_email_domain, get_realm_by_string_id, \
    get_unique_open_realm, email_to_domain, email_allowed_for_realm
from zproject.backends import password_auth_enabled

import logging
import re
import DNS

from typing import Any, Callable, Optional, Text

MIT_VALIDATION_ERROR = u'That user does not exist at MIT or is a ' + \
                       u'<a href="https://ist.mit.edu/email-lists">mailing list</a>. ' + \
                       u'If you want to sign up an alias for Zulip, ' + \
                       u'<a href="mailto:support@zulipchat.com">contact us</a>.'
WRONG_SUBDOMAIN_ERROR = "Your Zulip account is not a member of the " + \
                        "organization associated with this subdomain.  " + \
                        "Please contact %s with any questions!" % (settings.ZULIP_ADMINISTRATOR,)

def get_registration_string(domain):
    # type: (Text) -> Text
    register_url  = reverse('register') + domain
    register_account_string = _('The organization with the domain already exists. '
                                'Please register your account <a href=%(url)s>here</a>.') % {'url': register_url}
    return register_account_string

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
                raise

class RegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    # The required-ness of the password field gets overridden if it isn't
    # actually required for a realm
    password = forms.CharField(widget=forms.PasswordInput, max_length=100,
                               required=False)
    realm_name = forms.CharField(max_length=100, required=False)
    realm_subdomain = forms.CharField(max_length=40, required=False)
    realm_org_type = forms.ChoiceField(((Realm.COMMUNITY, 'Community'),
                                        (Realm.CORPORATE, 'Corporate')),
                                       initial=Realm.COMMUNITY, required=False)

    if settings.TERMS_OF_SERVICE:
        terms = forms.BooleanField(required=True)

    def clean_realm_subdomain(self):
        # type: () -> str
        if settings.REALMS_HAVE_SUBDOMAINS:
            error_strings = {
                'too short': _("Subdomain needs to have length 3 or greater."),
                'extremal dash': _("Subdomain cannot start or end with a '-'."),
                'bad character': _("Subdomain can only have lowercase letters, numbers, and '-'s."),
                'unavailable': _("Subdomain unavailable. Please choose a different one.")}
        else:
            error_strings = {
                'too short': _("Short name needs at least 3 characters."),
                'extremal dash': _("Short name cannot start or end with a '-'."),
                'bad character': _("Short name can only have lowercase letters, numbers, and '-'s."),
                'unavailable': _("Short name unavailable. Please choose a different one.")}
        subdomain = self.cleaned_data['realm_subdomain']
        if not subdomain:
            return ''
        if len(subdomain) < 3:
            raise ValidationError(error_strings['too short'])
        if subdomain[0] == '-' or subdomain[-1] == '-':
            raise ValidationError(error_strings['extremal dash'])
        if not re.match('^[a-z0-9-]*$', subdomain):
            raise ValidationError(error_strings['bad character'])
        if is_reserved_subdomain(subdomain) or \
           get_realm_by_string_id(subdomain) is not None:
            raise ValidationError(error_strings['unavailable'])
        return subdomain

class ToSForm(forms.Form):
    terms = forms.BooleanField(required=True)

class HomepageForm(forms.Form):
    email = forms.EmailField(validators=[is_inactive])

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        self.realm = kwargs.pop('realm', None)
        super(HomepageForm, self).__init__(*args, **kwargs)

    def clean_email(self):
        # type: () -> str
        """Returns the email if and only if the user's email address is
        allowed to join the realm they are trying to join."""
        email = self.cleaned_data['email']

        if get_unique_open_realm():
            return email

        # Otherwise, the user is trying to join a specific realm.
        realm = self.realm
        if realm is None and not settings.REALMS_HAVE_SUBDOMAINS:
            realm = get_realm_by_email_domain(email)

        if realm is None:
            if settings.REALMS_HAVE_SUBDOMAINS:
                raise ValidationError(_("The organization you are trying to join does not exist."))
            else:
                raise ValidationError(_("Your email address does not correspond to any existing organization."))

        if realm.invite_required:
            raise ValidationError(_("Please request an invite from the organization administrator."))

        if not email_allowed_for_realm(email, realm):
            raise ValidationError(
                _("The organization you are trying to join, %(string_id)s, only allows users with e-mail "
                  "addresses within the organization. Please try a different e-mail address."
                  % {'string_id': realm.string_id}))

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
                           log=True, commit=commit)
        return self.user

class ZulipPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        # type: (str) -> QuerySet
        """Given an email, return matching user(s) who should receive a reset.

        This is modified from the original in that it allows non-bot
        users who don't have a usable password to reset their
        passwords.
        """
        if not password_auth_enabled:
            logging.info("Password reset attempted for %s even though password auth is disabled." % (email,))
            return []
        result = UserProfile.objects.filter(email__iexact=email, is_active=True,
                                            is_bot=False)
        if len(result) == 0:
            logging.info("Password reset attempted for %s; no active account." % (email,))
        return result

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
                settings.ZULIP_ADMINISTRATOR)
            raise ValidationError(mark_safe(error_msg))

        if not check_subdomain(get_subdomain(self.request), user_profile.realm.subdomain):
            logging.warning("User %s attempted to password login to wrong subdomain %s" %
                            (user_profile.email, get_subdomain(self.request)))
            raise ValidationError(mark_safe(WRONG_SUBDOMAIN_ERROR))
        return email
