# -*- coding: utf-8 -*-
import hashlib
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

        if i != limit - 1:
            sleep(sleep_time)

def make_safe_digest(string, hash_func=hashlib.sha1):
    """
    return a hex digest of `string`.
    """
    # hashlib.sha1, md5, etc. expect bytes, so non-ASCII strings must
    # be encoded.
    return hash_func(string.encode('utf-8')).hexdigest()
