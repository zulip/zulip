from __future__ import absolute_import

from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.contrib.auth.forms import SetPasswordForm, AuthenticationForm
from django.conf import settings

from zerver.models import Realm, get_user_profile_by_email, UserProfile, \
    completely_open, resolve_email_to_domain, get_realm
from zerver.lib.actions import do_change_password, is_inactive
from zproject.backends import password_auth_enabled
import DNS

SIGNUP_STRING = u'Your e-mail does not match any existing open organization. ' + \
                u'Use a different e-mail address, or contact %s with questions.' % (settings.ZULIP_ADMINISTRATOR,)
if settings.ZULIP_COM:
    SIGNUP_STRING = u'Your e-mail does not match any existing organization. <br />' + \
                    u"The zulip.com service is not taking new customer teams. <br /> " + \
                    u"<a href=\"https://blogs.dropbox.com/tech/2015/09/open-sourcing-zulip-a-dropbox-hack-week-project/\">Zulip is open source</a>, so you can install your own Zulip server " + \
                    u"by following the instructions on <a href=\"https://www.zulip.org\">www.zulip.org</a>!"

def has_valid_realm(value):
    # Checks if there is a realm without invite_required
    # matching the domain of the input e-mail.
    realm = get_realm(resolve_email_to_domain(value))
    return realm is not None and not realm.invite_required

def not_mit_mailing_list(value):
    # I don't want ec-discuss signed up for Zulip
    if "@mit.edu" in value:
        username = value.rsplit("@", 1)[0]
        # Check whether the user exists and can get mail.
        try:
            DNS.dnslookup("%s.pobox.ns.athena.mit.edu" % username, DNS.Type.TXT)
            return True
        except DNS.Base.ServerError as e:
            if e.rcode == DNS.Status.NXDOMAIN:
                raise ValidationError(mark_safe(u'That user does not exist at MIT or is a <a href="https://ist.mit.edu/email-lists">mailing list</a>. If you want to sign up an alias for Zulip, <a href="mailto:support@zulip.com">contact us</a>.'))
            else:
                raise
    return True

class RegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    # The required-ness of the password field gets overridden if it isn't
    # actually required for a realm
    password = forms.CharField(widget=forms.PasswordInput, max_length=100,
                               required=False)
    if not settings.VOYAGER:
        terms = forms.BooleanField(required=True)


class ToSForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    terms = forms.BooleanField(required=True)

class HomepageForm(forms.Form):
    # This form is important because it determines whether users can
    # register for our product. Be careful when modifying the
    # validators.
    email = forms.EmailField(validators=[is_inactive,])

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.get("domain")
        if "domain" in kwargs:
            del kwargs["domain"]
        super(HomepageForm, self).__init__(*args, **kwargs)

    def clean_email(self):
        data = self.cleaned_data['email']
        if completely_open(self.domain) or has_valid_realm(data) and not_mit_mailing_list(data):
            return data
        raise ValidationError(mark_safe(SIGNUP_STRING))

class LoggingSetPasswordForm(SetPasswordForm):
    def save(self, commit=True):
        do_change_password(self.user, self.cleaned_data['new_password1'],
                           log=True, commit=commit)
        return self.user

class CreateUserForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    email = forms.EmailField()

class OurAuthenticationForm(AuthenticationForm):
    def clean_username(self):
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
