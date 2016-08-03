from datetime import datetime, timedelta

# what is the scope of this?
INTERVAL_NAMES = {'hour' : 3600, 'day' : 86400, 'gauge' : None}

class AnalyticsInterval:
    def __init__(self, name, end = datetime.utcnow(), round_to_boundary = 'hour'):
        if round_to_boundary is not None:
            self.end = interval_boundary_floor(end, round_to_boundary)
        if name not in INTERVAL_NAMES:
            raise ValueError('%s is not a valid interval name' % name)
        self.name = name
        if name == 'gauge':
            self.start = datetime(year = datetime.MINYEAR)
        else:
            self.start = self.end - timedelta(seconds = INTERVAL_NAMES[name])
    # add way to init with start_time and end_time, and no interval


def interval_boundary_floor(datetime_object, interval_name):
    # type: (datetime, text_type) -> datetime
    # don't have to worry about leap seconds, since datetime doesn't support it
    # datetime objects are (year, month, day, hour, minutes, seconds, microseconds)
    if interval_name == 'hour':
        return datetime(*datetime_object.timetuple()[:4])
    elif interval_name == 'day':
        return datetime(*datetime_object.timetuple()[:3])
    else:
        raise ValueError("Unknown interval name", interval_name)


# delete rest of below ..?
def interval_boundary_next(datetime_object, interval):
    # type: (datetime, text_type) -> datetime
    # don't have to worry about leap seconds, since datetime doesn't support it
    # datetime objects are (year, month, day, hour, minutes, seconds, microseconds)
    last = interval_boundary_floor(datetime_object, interval)
    if interval == 'hour':
        return last + timedelta(hour = 1)
    elif interval == 'day':
        return last + timedelta(day = 1)
    else:
        raise ValueError("Unknown interval", interval)

def interval_boundary_lastfloor(datetime_object, interval):
    # type: (datetime, text_type) -> datetime
    last = interval_boundary_floor(datetime_object, interval)
    return interval_boundary_lastfloor(last - timedelta(microseconds = 1), interval)

def interval_boundaries(datetime_object, interval):
    # type: (datetime, text_type) -> Tuple[datetime, datetime]
    if interval == 'hour':
        start = datetime(*datetime_object.timetuple()[:4])
        end = start + timedelta(hour = 1)
    elif interval == 'day':
        start = datetime(*datetime_object.timetuple()[:3])
        end = start + timedelta(day = 1)
    else:
        raise ValueError("Unknown interval", interval)
    return (start, end)

def prev_interval_boundaries(datetime_object, interval):
    # type: (datetime, text_type) -> Tuple[datetime, datetime]
    if interval == 'hour':
        end = datetime(*datetime_object.timetuple()[:4])
        start = end - timedelta(hour = 1)
    elif interval == 'day':
        end = datetime(*datetime_object.timetuple()[:3])
        start = end - timedelta(day = 1)
    else:
        raise ValueError("Unknown interval", interval)
    return (start, end)
