from __future__ import absolute_import
from typing import Any, Callable, Optional

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import SetPasswordForm, AuthenticationForm, \
    PasswordResetForm
from django.conf import settings
from django.db.models.query import QuerySet
from jinja2 import Markup as mark_safe
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _

import logging

from zerver.models import Realm, get_user_profile_by_email, UserProfile, \
    completely_open, resolve_email_to_domain, get_realm, \
    get_unique_open_realm, split_email_to_domain
from zerver.lib.actions import do_change_password, is_inactive, user_email_is_unique
from zproject.backends import password_auth_enabled
import DNS
from six import text_type

SIGNUP_STRING = u'Your e-mail does not match any existing open organization. ' + \
                u'Use a different e-mail address, or contact %s with questions.' % (settings.ZULIP_ADMINISTRATOR,)
if settings.SHOW_OSS_ANNOUNCEMENT:
    SIGNUP_STRING = u'Your e-mail does not match any existing organization. <br />' + \
                    u"The zulip.com service is not taking new customer teams. <br /> " + \
                    u"<a href=\"https://blogs.dropbox.com/tech/2015/09/open-sourcing-zulip-a-dropbox-hack-week-project/\">" + \
                    u"Zulip is open source</a>, so you can install your own Zulip server " + \
                    u"by following the instructions on <a href=\"https://www.zulip.org\">www.zulip.org</a>!"
MIT_VALIDATION_ERROR = u'That user does not exist at MIT or is a ' + \
                       u'<a href="https://ist.mit.edu/email-lists">mailing list</a>. ' + \
                       u'If you want to sign up an alias for Zulip, ' + \
                       u'<a href="mailto:"' + settings.ZULIP_ADMINISTRATOR + '">contact us</a>.'

def get_registration_string(domain):
    # type: (text_type) -> text_type
    register_url  = reverse('register') + domain
    register_account_string = _('The organization with the domain already exists. '
                                'Please register your account <a href=%(url)s>here</a>.') % {'url': register_url}
    return register_account_string

def get_valid_realm(value):
    # type: (str) -> Optional[Realm]
    """Checks if there is a realm without invite_required
    matching the domain of the input e-mail."""
    realm = get_realm(resolve_email_to_domain(value))
    if realm is None or realm.invite_required:
        return None
    return realm

def not_mit_mailing_list(value):
    # type: (str) -> bool
    """Prevent MIT mailing lists from signing up for Zulip"""
    if "@mit.edu" in value:
        username = value.rsplit("@", 1)[0]
        # Check whether the user exists and can get mail.
        try:
            DNS.dnslookup("%s.pobox.ns.athena.mit.edu" % username, DNS.Type.TXT)
            return True
        except DNS.Base.ServerError as e:
            if e.rcode == DNS.Status.NXDOMAIN:
                raise ValidationError(mark_safe(MIT_VALIDATION_ERROR))
            else:
                raise
    return True

class RegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    # The required-ness of the password field gets overridden if it isn't
    # actually required for a realm
    password = forms.CharField(widget=forms.PasswordInput, max_length=100,
                               required=False)
    realm_name = forms.CharField(max_length=100, required=False)

    if settings.TERMS_OF_SERVICE:
        terms = forms.BooleanField(required=True)

class ToSForm(forms.Form):
    terms = forms.BooleanField(required=True)

class HomepageForm(forms.Form):
    # This form is important because it determines whether users can
    # register for our product. Be careful when modifying the
    # validators.
    email = forms.EmailField(validators=[is_inactive,])

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        self.domain = kwargs.get("domain")
        if "domain" in kwargs:
            del kwargs["domain"]
        super(HomepageForm, self).__init__(*args, **kwargs)

    def clean_email(self):
        # type: () -> str
        """Returns the email if and only if the user's email address is
        allowed to join the realm they are trying to join."""
        data = self.cleaned_data['email']
        # If the server has a unique open realm, pass
        if get_unique_open_realm():
            return data

        # If a realm is specified and that realm is open, pass
        if completely_open(self.domain):
            return data

        # If no realm is specified, fail
        realm = get_valid_realm(data)
        if realm is None:
            raise ValidationError(mark_safe(SIGNUP_STRING))

        # If it's a clear realm not used for Zephyr mirroring, pass
        if not realm.is_zephyr_mirror_realm:
            return data

        # At this point, the user is trying to join a Zephyr mirroring
        # realm.  We confirm that they are a real account (not a
        # mailing list), and if so, let them in.
        if not_mit_mailing_list(data):
            return data

        # Otherwise, the user is an MIT mailing list, and we return failure
        raise ValidationError(mark_safe(SIGNUP_STRING))

class RealmCreationForm(forms.Form):
    # This form determines whether users can
    # create a new realm. Be careful when modifying the
    # validators.
    email = forms.EmailField(validators=[user_email_is_unique,])

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        self.domain = kwargs.get("domain")
        if "domain" in kwargs:
            del kwargs["domain"]
        super(RealmCreationForm, self).__init__(*args, **kwargs)

    def clean_email(self):
        # type: () -> text_type
        data = self.cleaned_data['email']
        domain = split_email_to_domain(data)
        if (get_realm(domain) is not None):
            raise ValidationError(mark_safe(get_registration_string(domain)))
        return data

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

        return email
