from argparse import ArgumentParser
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now

from analytics.models import InstallationCount, installation_epoch, \
    last_successful_fill
from analytics.lib.counts import COUNT_STATS, CountStat
from zerver.lib.timestamp import floor_to_hour, floor_to_day, verify_UTC, \
    TimezoneNotUTCException
from zerver.models import Realm

import os
import subprocess
import sys
import time
from typing import Any, Dict

states = {
    0: "OK",
    1: "WARNING",
    2: "CRITICAL",
    3: "UNKNOWN"
}

class Command(BaseCommand):
    help = """Checks FillState table.

    Run as a cron job that runs every hour."""

    def handle(self, *args: Any, **options: Any) -> None:
        fill_state = self.get_fill_state()
        status = fill_state['status']
        message = fill_state['message']

        state_file_path = "/var/lib/nagios_state/check-analytics-state"
        state_file_tmp = state_file_path + "-tmp"

        with open(state_file_tmp, "w") as f:
            f.write("%s|%s|%s|%s\n" % (
                int(time.time()), status, states[status], message))
        subprocess.check_call(["mv", state_file_tmp, state_file_path])

    def get_fill_state(self) -> Dict[str, Any]:
        if not Realm.objects.exists():
            return {'status': 0, 'message': 'No realms exist, so not checking FillState.'}

        warning_unfilled_properties = []
        critical_unfilled_properties = []
        for property, stat in COUNT_STATS.items():
            last_fill = last_successful_fill(property)
            if last_fill is None:
                last_fill = installation_epoch()
            try:
                verify_UTC(last_fill)
            except TimezoneNotUTCException:
                return {'status': 2, 'message': 'FillState not in UTC for %s' % (property,)}

            if stat.frequency == CountStat.DAY:
                floor_function = floor_to_day
                warning_threshold = timedelta(hours=26)
                critical_threshold = timedelta(hours=50)
            else:  # CountStat.HOUR
                floor_function = floor_to_hour
                warning_threshold = timedelta(minutes=90)
                critical_threshold = timedelta(minutes=150)

            if floor_function(last_fill) != last_fill:
                return {'status': 2, 'message': 'FillState not on %s boundary for %s' %
                        (stat.frequency, property)}

            time_to_last_fill = timezone_now() - last_fill
            if time_to_last_fill > critical_threshold:
                critical_unfilled_properties.append(property)
            elif time_to_last_fill > warning_threshold:
                warning_unfilled_properties.append(property)

        if len(critical_unfilled_properties) == 0 and len(warning_unfilled_properties) == 0:
            return {'status': 0, 'message': 'FillState looks fine.'}
        if len(critical_unfilled_properties) == 0:
            return {'status': 1, 'message': 'Missed filling %s once.' %
                    (', '.join(warning_unfilled_properties),)}
        return {'status': 2, 'message': 'Missed filling %s once. Missed filling %s at least twice.' %
                (', '.join(warning_unfilled_properties), ', '.join(critical_unfilled_properties))}
