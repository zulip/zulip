# -*- coding: utf-8 -*-
from time import sleep

# Runs the callback with slices of all_list of a given batch_size
def run_in_batches(all_list, batch_size, callback, sleep_time = 0, logger = None):
    if len(all_list) == 0:
        return

    limit = (len(all_list) / batch_size) + 1;
    for i in xrange(limit):
        start = i*batch_size
        end = (i+1) * batch_size
        if end >= len(all_list):
            end = len(all_list)
        batch = all_list[start:end]

        if logger:
            logger("Executing %s in batch %s of %s" % (end-start, i+1, limit))

        callback(batch)
        sleep(sleep_time)
