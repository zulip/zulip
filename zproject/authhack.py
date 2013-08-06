# Hack to allow longer-than-72-characters inputs into "username" forms
#
# This is needed because we're using the email address as the "username".
#
# This code can go away once we switch to Django 1.5 with pluggable
# user models
#
# Adapted from https://gist.github.com/1143957
from django.conf import settings

import sys

USERNAME_MAXLENGTH = getattr(settings, 'USERNAME_MAXLENGTH', 72)

def hack_forms(length=USERNAME_MAXLENGTH, forms=[
        'django.contrib.auth.forms.UserCreationForm',
        'django.contrib.auth.forms.UserChangeForm',
        'django.contrib.auth.forms.AuthenticationForm',
    ]):
    """
    Hacks username length in django forms.
    """
    for form in forms:
        modulename, sep, classname = form.rpartition('.')
        if not modulename in sys.modules:
            __import__(modulename)
        module = sys.modules[modulename]
        klass = getattr(module, classname)
        hack_single_form(klass, length)

def hack_single_form(form_class, length=USERNAME_MAXLENGTH):
    if hasattr(form_class, 'declared_fields'):
        fields = form_class.declared_fields
    elif hasattr(form_class, 'base_fields'):
        fields = form_class.base_fields
    else:
        raise TypeError('Provided object: %s doesnt seem to be a valid Form or '
                        'ModelForm class.' % form_class)
    username = fields['username']
    hack_validators(username.validators)
    username.max_length = length
    username.widget.attrs['maxlength'] = length

def hack_validators(validators, length=USERNAME_MAXLENGTH):
    from django.core.validators import MaxLengthValidator
    for key, validator in enumerate(validators):
        if isinstance(validator, MaxLengthValidator):
            validators.pop(key)
    validators.insert(0, MaxLengthValidator(length))

hack_forms()
