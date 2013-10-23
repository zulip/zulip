from django.db import models
import zerver.models

def get_deployment_by_domain(domain):
    return Deployment.objects.get(realms__domain=domain)

class Deployment(models.Model):
    realms = models.ManyToManyField(zerver.models.Realm, related_name="_deployments")
    is_active = models.BooleanField(default=True)

    # TODO: This should really become the public portion of a keypair, and
    # it should be settable only with an initial bearer "activation key"
    api_key = models.CharField(max_length=32, null=True)

    base_api_url = models.CharField(max_length=128)
    base_site_url = models.CharField(max_length=128)

    @property
    def endpoints(self):
        return {'base_api_url': self.base_api_url, 'base_site_url': self.base_site_url}
