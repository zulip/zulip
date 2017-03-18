from django.db import models
from django.db.models import Manager
from typing import Dict, Text

import zerver.models

def get_deployment_by_domain(realm_str):
    # type: (Text) -> Deployment
    return Deployment.objects.get(realms__string_id=realm_str)

class Deployment(models.Model):
    realms = models.ManyToManyField(zerver.models.Realm,
                                    related_name="_deployments") # type: Manager
    is_active = models.BooleanField(default=True) # type: bool

    # TODO: This should really become the public portion of a keypair, and
    # it should be settable only with an initial bearer "activation key"
    api_key = models.CharField(max_length=32, null=True) # type: Text

    base_api_url = models.CharField(max_length=128) # type: Text
    base_site_url = models.CharField(max_length=128) # type: Text

    @property
    def endpoints(self):
        # type: () -> Dict[str, Text]
        return {'base_api_url': self.base_api_url, 'base_site_url': self.base_site_url}

    @property
    def name(self):
        # type: () -> Text

        # TODO: This only does the right thing for prod because prod authenticates to
        # staging with the zulip.com deployment key, while staging is technically the
        # deployment for the zulip.com realm.
        # This also doesn't necessarily handle other multi-realm deployments correctly.
        return self.realms.order_by('pk')[0].domain
