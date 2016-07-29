from django.db import models

from zerver.lib.str_utils import ModelReprMixin

class RealmCount(ModelReprMixin, models.Model):
    domain = models.CharField(max_length=40, db_index=True) # type: text_type
    # Is this a problem if we ever need to split the databases in the future?
    realm = models.ForeignKey(Realm) # type: Realm
    property = models.CharField(max_length=40) # type: text_type
    value = models.BigIntegerField() # type: int
    start_time = models.DateTimeField() # type: datetime.datetime
    interval = models.CharField(max_length=20) # type: text_type
    anomaly_id = models.BigIntegerField(null=True) # type: Optional[int]
