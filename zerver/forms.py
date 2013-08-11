from __future__ import absolute_import

from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.contrib.auth.forms import SetPasswordForm

from zproject import settings
from zerver.models import Realm, get_user_profile_by_email, UserProfile, \
    completely_open
from zerver.lib.actions import do_change_password
import DNS

def is_inactive(value):
    try:
        if get_user_profile_by_email(value).is_active:
            raise ValidationError(u'%s is already active' % value)
    except UserProfile.DoesNotExist:
        pass

SIGNUP_STRING = '<a href="https://zulip.com/signup">Sign up</a> to find out when Zulip is ready for you.'

def has_valid_realm(value):
    return Realm.objects.filter(domain=value.split("@")[-1]).exists()

def isnt_mit(value):
    if "@mit.edu" in value:
        raise ValidationError(mark_safe(u'Zulip for MIT is by invitation only. ' + SIGNUP_STRING))

def not_mit_mailing_list(value):
    # I don't want ec-discuss signed up for Zulip
    if "@mit.edu" in value:
        username = value.rsplit("@", 1)[0]
        # Check whether the user exists and can get mail.
        try:
            DNS.dnslookup("%s.pobox.ns.athena.mit.edu" % username, DNS.Type.TXT)
            return True
        except DNS.Base.ServerError, e:
            if e.rcode == DNS.Status.NXDOMAIN:
                raise ValidationError(mark_safe(u'That user does not exist at MIT or is a <a href="https://ist.mit.edu/email-lists">mailing list</a>. If you want to sign up an alias for Zulip, <a href="mailto:support@zulip.com">contact us</a>.'))
            else:
                raise
    return True

class RegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    password = forms.CharField(widget=forms.PasswordInput, max_length=100)
    terms = forms.BooleanField(required=True)

class ToSForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    terms = forms.BooleanField(required=True)

class HomepageForm(forms.Form):
    # This form is important because it determines whether users can
    # register for our product. Be careful when modifying the
    # validators.
    if settings.ALLOW_REGISTER:
        email = forms.EmailField()
    else:
        validators = [is_inactive]
        email = forms.EmailField(validators=validators)

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.get("domain")
        if kwargs.has_key("domain"):
            del kwargs["domain"]
        super(HomepageForm, self).__init__(*args, **kwargs)

    def clean_email(self):
        data = self.cleaned_data['email']
        if completely_open(self.domain) or has_valid_realm(data) and not_mit_mailing_list(data):
            return data
        raise ValidationError(mark_safe(
                u'Registration is not currently available for your domain. ' \
                    + SIGNUP_STRING))

class LoggingSetPasswordForm(SetPasswordForm):
    def save(self, commit=True):
        do_change_password(self.user, self.cleaned_data['new_password1'],
                           log=True, commit=commit)
        return self.user

class CreateBotForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    email = forms.EmailField()
