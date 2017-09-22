import uuid
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from zilencer.models import MAX_HOST_NAME_LENGTH, API_KEY_LENGTH, \
    RemoteZulipServer, get_remote_server_by_uuid, UUID_LENGTH

class EnterpriseToSForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    company = forms.CharField(max_length=100)
    terms = forms.BooleanField(required=True)

class StartRemoteServerRegistrationForm(forms.Form):
    email = forms.EmailField(required=True)

class RemoteServerRegistrationForm(forms.Form):
    zulip_org_id = forms.CharField(max_length=UUID_LENGTH, required=True)
    zulip_org_key = forms.CharField(max_length=API_KEY_LENGTH, required=True)
    hostname = forms.URLField(max_length=MAX_HOST_NAME_LENGTH)
    terms = forms.BooleanField(required=True)

    def clean_zulip_org_id(self):
        # type: () -> None
        zulip_org_id = self.cleaned_data['zulip_org_id']
        try:
            uuid.UUID(zulip_org_id)
        except ValueError:
            raise ValidationError(_('Enter a valid UUID.'))

        if RemoteZulipServer.objects.filter(uuid=zulip_org_id).exists():
            raise ValidationError(_("Zulip organization id already exists."))
        return zulip_org_id

    def clean_hostname(self):
        # type: () -> None
        hostname = self.cleaned_data['hostname']
        if not hostname.startswith('https://'):
            raise ValidationError(_("Hostname should start with https://."))

        if RemoteZulipServer.objects.filter(hostname=hostname).exists():
            raise ValidationError(
                _("{hostname} has already been registered.").format(
                    hostname=hostname))
        return hostname
