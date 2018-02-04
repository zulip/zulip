from django import forms

class EnterpriseToSForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    company = forms.CharField(max_length=100)
    terms = forms.BooleanField(required=True)
