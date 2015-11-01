"""monthdelta

Date calculation with months: MonthDelta class and monthmod() function.
"""

__all__ = ['MonthDelta', 'monthmod']

from datetime import date, timedelta

class MonthDelta:
    """Number of months offset from a date or datetime.

    MonthDeltas allow date calculation without regard to the different lengths
    of different months. A MonthDelta value added to a date produces another
    date that has the same day-of-the-month, regardless of the lengths of the
    intervening months. If the resulting date is in too short a month, the
    last day in that month will result:

        date(2008,1,30) + MonthDelta(1) -> date(2008,2,29)

    MonthDeltas may be added, subtracted, multiplied, and floor-divided
    similarly to timedeltas. They may not be added to timedeltas directly, as
    both classes are intended to be used directly with dates and datetimes.
    Only ints may be passed to the constructor. MonthDeltas are immutable.

    NOTE: in calculations involving the 29th, 30th, and 31st days of the
    month, MonthDeltas are not necessarily invertible [i.e., the result above
    would not imply that date(2008,2,29) - MonthDelta(1) -> date(2008,1,30)].
    """
    __slots__ = ('__months',)

    def __init__(self, months=1):
        if not isinstance(months, int):
            raise TypeError('months must be an integer')
        self.__months = months
    def months(self):
        return self.__months
    months = property(months)
    def __repr__(self):
        try:
            return 'MonthDelta({0})'.format(self.__months)
        except AttributeError:
            return 'MonthDelta(' + str(self.__months) + ')'
    def __str__(self):
        return str(self.__months) + ' month' + ((abs(self.__months) != 1
                                                 and 's') or '')
    def __hash__(self):
        return hash(self.__months)
    def __eq__(self, other):
        if isinstance(other, MonthDelta):
            return (self.__months == other.months)
        return False
    def __ne__(self, other):
        if isinstance(other, MonthDelta):
            return (self.__months != other.months)
        return True
    def __lt__(self, other):
        if isinstance(other, MonthDelta):
            return (self.__months < other.months)
        return NotImplemented
    def __le__(self, other):
        if isinstance(other, MonthDelta):
            return (self.__months <= other.months)
        return NotImplemented
    def __gt__(self, other):
        if isinstance(other, MonthDelta):
            return (self.__months > other.months)
        return NotImplemented
    def __ge__(self, other):
        if isinstance(other, MonthDelta):
            return (self.__months >= other.months)
        return NotImplemented
    def __add__(self, other):
        if isinstance(other, MonthDelta):
            return MonthDelta(self.__months + other.months)
        if isinstance(other, date):
            day = other.day
            # subract one because months are not zero-based
            month = other.month + self.__months - 1
            year = other.year + month // 12
            # now add it back
            month = month % 12 + 1
            if month == 2:
                if day >= 29 and not year%4 and (year%100 or not year%400):
                    day = 29
                elif day > 28:
                    day = 28
            elif month in (4, 6, 9, 11) and day > 30:
                day = 30
            try:
                return other.replace(year, month, day)
            except ValueError:
                raise OverflowError('date value out of range')
        return NotImplemented
    def __sub__(self, other):
        if isinstance(other, MonthDelta):
            return MonthDelta(self.__months - other.months)
        return NotImplemented
    def __mul__(self, other):
        if isinstance(other, int):
            return MonthDelta(self.__months * other)
        return NotImplemented
    def __floordiv__(self, other):
        # MonthDelta // MonthDelta -> int
        if isinstance(other, MonthDelta):
            return self.__months // other.months
        if isinstance(other, int):
            return MonthDelta(self.__months // other)
        return NotImplemented
    def __radd__(self, other):
        return self + other
    def __rsub__(self, other):
        return -self + other
    def __rmul__(self, other):
        return self * other
    def __ifloordiv__(self, other):
        # in-place division by a MonthDelta (which will change the variable's
        # type) is almost certainly a bug -- raising this error is the reason
        # we don't just fall back on __floordiv__
        if isinstance(other, MonthDelta):
            raise TypeError('in-place division of a MonthDelta requires an '
                            'integer divisor')
        if isinstance(other, int):
            return MonthDelta(self.__months // other)
        return NotImplemented
    def __neg__(self):
        return MonthDelta(-self.__months)
    def __pos__(self):
        return MonthDelta(+self.__months)
    def __abs__(self):
        return MonthDelta(abs(self.__months))
    def __bool__(self):
        return bool(self.__months)
    __nonzero__ = __bool__

def monthmod(start, end):
    """Months between dates, plus leftover time.

    Distribute the interim between start and end dates into MonthDelta and
    timedelta portions. If and only if start is after end, returned MonthDelta
    will be negative. Returned timedelta is always non-negative, and is always
    smaller than the month in which the end date occurs.

    Invariant: dt + monthmod(dt, dt+td)[0] + monthmod(dt, dt+td)[1] = dt + td
    """
    if not (isinstance(start, date) and isinstance(end, date)):
        raise TypeError('start and end must be dates')
    md = MonthDelta(12*(end.year - start.year) + end.month - start.month -
                    int(start.day > end.day))
    # will overflow (underflow?) for end near date.min
    return md, end - (start + md)
