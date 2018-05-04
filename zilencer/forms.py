from django import forms

class EnterpriseToSForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    company = forms.CharField(max_length=100)
    terms = forms.BooleanField(required=True)

class RemoteServerRegistrationForm(forms.Form):
    uuid = forms.CharField(min_length=36, max_length=36)
    api_key = forms.CharField(min_length=64, max_length=64)
    hostname = forms.CharField(max_length=128)
    contact_email = forms.EmailField()
    terms = forms.BooleanField(required=True)
