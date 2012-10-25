from django import forms
from django.core import validators
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

def is_unique(value):
    try:
        User.objects.get(email=value)
        raise ValidationError(u'%s is already registered' % value)
    except User.DoesNotExist:
        pass

class UniqueEmailField(forms.EmailField):
    default_validators = [validators.validate_email, is_unique]

class RegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    password = forms.CharField(widget=forms.PasswordInput, max_length=100)
    domain = forms.CharField(max_length=100)
    terms = forms.BooleanField(required=True)

class HomepageForm(forms.Form):
    email = UniqueEmailField()
