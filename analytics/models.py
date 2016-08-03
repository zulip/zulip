from django.db import models

from zerver.models import Realm, UserProfile
from zerver.lib.str_utils import ModelReprMixin

class RealmCount(ModelReprMixin, models.Model):
    realm = models.ForeignKey(Realm) # type: Realm
    property = models.CharField(max_length=40) # type: text_type
    value = models.BigIntegerField() # type: int
    end_time = models.DateTimeField() # type: datetime.datetime
    interval = models.CharField(max_length=20) # type: text_type
    anomaly = models.ForeignKey(Anomaly, null=True) # type: Optional[Anomaly]

    def __unicode__(self):
        # type: () -> text_type
        return u"<RealmCount: %s %s %d %s>" % (self.realm, self.property, self.value, self.id)

class UserCount(ModelReprMixin, models.Model):
    # Is this a problem if we ever need to split the databases in the future?
    realm = models.ForeignKey(Realm) # type: Realm
    user = models.ForeignKey(UserProfile) # type: UserProfile
    property = models.CharField(max_length=40) # type: text_type
    value = models.BigIntegerField() # type: int
    end_time = models.DateTimeField() # type: datetime.datetime
    interval = models.CharField(max_length=20) # type: text_type
    anomaly = models.ForeignKey(Anomaly, null=True) # type: Optional[Anomaly]

    def __unicode__(self):
        # type: () -> text_type
        return u"<UserCount: %s %s %d %s>" % (self.user, self.property, self.value, self.id)

class Anomaly(ModelReprMixin, models.Model):
    info = models.CharField() # type: text_type

    def __unicode__(self):
        # type: () -> text_type
        return u"<Anamoly: %s... %s>" % (self.info, self.id)
