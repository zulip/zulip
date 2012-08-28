from django import forms

class RegistrationForm(forms.Form):
    username = forms.CharField(max_length=100)
    password = forms.CharField(max_length=100)
