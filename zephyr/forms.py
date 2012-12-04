from django import forms
from django.core import validators
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils.safestring import mark_safe

from humbug import settings
from models import Realm

def is_unique(value):
    try:
        User.objects.get(email__iexact=value)
        raise ValidationError(u'%s is already registered' % value)
    except User.DoesNotExist:
        pass

def is_active(value):
    try:
        if User.objects.get(email=value).is_active:
            raise ValidationError(u'%s is already active' % value)
    except User.DoesNotExist:
        pass

SIGNUP_STRING = '<a href="http://get.humbughq.com/">Sign up</a> to find out when Humbug is ready for you.'

def has_valid_realm(value):
    try:
        Realm.objects.get(domain=value.split("@")[-1])
    except Realm.DoesNotExist:
        raise ValidationError(mark_safe(u'Registration is not currently available for your domain. ' + SIGNUP_STRING))

def isnt_mit(value):
    if "@mit.edu" in value:
        raise ValidationError(mark_safe(u'Humbug for MIT is by invitation only. ' + SIGNUP_STRING))


class UniqueEmailField(forms.EmailField):
    default_validators = [validators.validate_email, is_unique]

class RegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    password = forms.CharField(widget=forms.PasswordInput, max_length=100)
    terms = forms.BooleanField(required=True)

class HomepageForm(forms.Form):
    if settings.ALLOW_REGISTER:
        email = UniqueEmailField()
    else:
        validators = UniqueEmailField.default_validators + [has_valid_realm, isnt_mit]
        email = UniqueEmailField(validators=validators)
