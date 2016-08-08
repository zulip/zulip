from django.db import models

from zerver.models import Realm, UserProfile, Stream
from zerver.lib.str_utils import ModelReprMixin

from analytics.lib.interval import MIN_TIME

class AnalyticsMixin(object):
    # should be the unique one first! TODO: explain what extended id is
    @staticmethod
    def extended_id():
        raise NotImplementedError

    @staticmethod
    def get_extended_ids_with_creation_from_zerver():
        raise NotImplementedError

    # hopefully we remember to handle this in a different way if we start
    # computing analytics at < 15 min resolution, or not on clean boundaries
    # setting to 15 min instead of 60, since there are timezones 30 and 45
    # min off of UTC
    _extended_ids_with_creation = None
    _extended_ids_last = MIN_TIME
    def get_extended_ids_with_creation(self, refresh = False):
        time_floored = floor_to_interval_boundary(timezone.now(), '15min')
        if refresh or self._extended_ids_with_creation is None or time_floored != self._extended_ids_last:
            self._extended_ids_with_creation  = list(self.get_extended_ids_with_creation_from_zerver())
            self._extended_ids_last = time_floored
            if len(self._extended_ids_with_creation) > 0:
                if set(self._extended_ids_with_creation[0].keys()) != set(extended_id + ('created',)):
                    raise ValueError("extended_id and get_extended_ids_with_creation are returning incompatible values.")
        return self._extended_ids_with_creation

# would only ever make entries here by hand
class Anomaly(ModelReprMixin, models.Model):
    info = models.CharField(max_length=1000) # type: text_type

    def __unicode__(self):
        # type: () -> text_type
        return u"<Anamoly: %s... %s>" % (self.info, self.id)

class BaseCount(ModelReprMixin, models.Model, AnalyticsMixin):
    value = models.BigIntegerField() # type: int
    property = models.CharField(max_length=40) # type: text_type
    end_time = models.DateTimeField() # type: datetime.datetime
    interval = models.CharField(max_length=20) # type: text_type
    anomaly = models.ForeignKey(Anomaly, null=True) # type: Optional[Anomaly]
    class Meta:
        abstract = True

class RealmCount(BaseCount):
    realm = models.ForeignKey(Realm) # type: Realm

    def extended_id():
        return ('realm_id',)

    def get_extended_ids_with_creation_from_zerver():
        return Realm.objects.annotate(realm_id='id', created='date_created') \
                            .values('realm_id', 'created')

    def __unicode__(self):
        # type: () -> text_type
        return u"<RealmCount: %s %s %d %s>" % (self.realm, self.property, self.value, self.id)

class UserCount(BaseCount):
    user = models.ForeignKey(UserProfile) # type: UserProfile
    realm = models.ForeignKey(Realm) # type: Realm

    def extended_id():
        return ('user_id', 'realm_id')

    def get_extended_ids_with_creation_from_zerver():
        return UserProfile.objects.annotate(user_id='id', created='date_joined') \
                                  .values('user_id', 'realm_id', 'created')
    def __unicode__(self):
        # type: () -> text_type
        return u"<UserCount: %s %s %d %s>" % (self.user, self.property, self.value, self.id)

class StreamCount(BaseCount):
    stream = models.ForeignKey(Stream) # type: Stream
    realm = models.ForeignKey(Realm) # type: Realm

    def extended_id():
        return ('stream_id', 'realm_id')

    def get_extended_ids_with_creation_from_zerver():
        return Stream.objects.annotate(stream_id='id', created='date_created') \
                             .values('stream_id', 'realm_id', 'created')

    def __unicode__(self):
        # type: () -> text_type
        return u"<StreamCount: %s %s %d %s>" % (self.stream, self.property, self.value, self.id)
