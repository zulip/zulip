from django.db import models

from zerver.models import Realm
from zerver.lib.str_utils import ModelReprMixin

class RealmCount(ModelReprMixin, models.Model):
    realm = models.ForeignKey(Realm) # type: Realm
    property = models.CharField(max_length=40) # type: text_type
    value = models.BigIntegerField() # type: int
    start_time = models.DateTimeField() # type: datetime.datetime
    interval = models.CharField(max_length=20) # type: text_type
    # will be a foreign key once the anomaly table is made
    anomaly_id = models.BigIntegerField(null=True) # type: Optional[int]

    def __unicode__(self):
        # type: () -> text_type
        return u"<RealmCount: %s %s %d %s>" % (self.realm__domain, self.property, self.value, self.id)

class UserCount(ModelReprMixin, models.Model):
    # Is this a problem if we ever need to split the databases in the future?
    realm = models.ForeignKey(Realm) # type: Realm
    user = models.ForeignKey(UserProfile) # type: UserProfile
    property = models.CharField(max_length=40) # type: text_type
    value = models.BigIntegerField() # type: int
    start_time = models.DateTimeField() # type: datetime.datetime
    interval = models.CharField(max_length=20) # type: text_type
    # will be a foreign key once the anomaly table is made
    anomaly_id = models.BigIntegerField(null=True) # type: Optional[int]

    def __unicode__(self):
        # type: () -> text_type
        return u"<RealmCount: %s %s %s %d %s>" % (self.user_email, self.realm__domain, self.property, self.value, self.id)
