#!/usr/bin/env python
import time

# Avoid requiring the typing module to be installed
if False: from typing import Tuple

def nagios_from_file(results_file):
    # type: (str) -> Tuple[int, str]
    """Returns a nagios-appropriate string and return code obtained by
    parsing the desired file on disk. The file on disk should be of format

    %s|%s % (timestamp, nagios_string)

    This file is created by various nagios checking cron jobs such as
    check-rabbitmq-queues and check-rabbitmq-consumers"""

    data = open(results_file).read().strip()
    pieces = data.split('|')

    if not len(pieces) == 4:
        state = 'UNKNOWN'
        ret = 3
        data = "Results file malformed"
    else:
        timestamp = int(pieces[0])

        time_diff = time.time() - timestamp
        if time_diff > 60 * 2:
            ret = 3
            state = 'UNKNOWN'
            data = "Results file is stale"
        else:
            ret = int(pieces[1])
            state = pieces[2]
            data = pieces[3]

    return (ret, "%s: %s" % (state, data))

