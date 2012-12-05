import datetime
from django.utils.timezone import utc

def timestamp_to_datetime(timestamp):
    return datetime.datetime.utcfromtimestamp(float(timestamp)).replace(tzinfo=utc)
