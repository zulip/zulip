from django.db import models

from zerver.models import Realm, UserProfile, Stream
from zerver.lib.str_utils import ModelReprMixin

from analytics.lib.interval import MIN_TIME

# would only ever make entries here by hand
class Anomaly(ModelReprMixin, models.Model):
    info = models.CharField(max_length=1000) # type: text_type

    def __unicode__(self):
        # type: () -> text_type
        return u"<Anamoly: %s... %s>" % (self.info, self.id)

class BaseCount(ModelReprMixin, models.Model):
    value = models.BigIntegerField() # type: int
    property = models.CharField(max_length=40) # type: text_type
    end_time = models.DateTimeField() # type: datetime.datetime
    interval = models.CharField(max_length=20) # type: text_type
    anomaly = models.ForeignKey(Anomaly, null=True) # type: Optional[Anomaly]
    class Meta:
        abstract = True

    @staticmethod
    def extended_id():
        raise NotImplementedError

    @staticmethod
    def key_model():
        raise NotImplementedError

    # future: could also have an aggregates_to function

class InstallationCount(BaseCount):
    def extended_id():
        return ()

    def key_model():
        return None

    def __unicode__(self):
        # type: () -> text_type
        return u"<InstallationCount: %s %s %s>" % (self.property, self.value, self.id)

class RealmCount(BaseCount):
    realm = models.ForeignKey(Realm) # type: Realm

    def extended_id():
        return ('realm_id',)

    def key_model():
        return Realm

    def __unicode__(self):
        # type: () -> text_type
        return u"<RealmCount: %s %s %s %s>" % (self.realm, self.property, self.value, self.id)

class UserCount(BaseCount):
    user = models.ForeignKey(UserProfile) # type: UserProfile
    realm = models.ForeignKey(Realm) # type: Realm

    def extended_id():
        return ('user_id', 'realm_id')

    def key_model():
        return UserProfile

    def __unicode__(self):
        # type: () -> text_type
        return u"<UserCount: %s %s %s %s>" % (self.user, self.property, self.value, self.id)

class StreamCount(BaseCount):
    stream = models.ForeignKey(Stream) # type: Stream
    realm = models.ForeignKey(Realm) # type: Realm

    def extended_id():
        return ('stream_id', 'realm_id')

    def key_model():
        return Stream

    def __unicode__(self):
        # type: () -> text_type
        return u"<StreamCount: %s %s %s %s>" % (self.stream, self.property, self.value, self.id)
