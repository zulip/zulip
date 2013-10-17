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
