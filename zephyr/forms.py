from django import forms

class RegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    short_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    username = forms.CharField(max_length=100)
    password = forms.CharField(widget=forms.PasswordInput, max_length=100)
