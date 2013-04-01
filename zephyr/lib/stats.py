import os
import logging

STATS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "stats")

def update_stat(name, value):
    try:
        os.mkdir(STATS_DIR)
    except OSError:
        pass

    base_filename = os.path.join(STATS_DIR, name)
    tmp_filename = base_filename + ".new"

    try:
        with file(tmp_filename, "w") as stat_file:
            stat_file.write("%s\n" % (str(value),))

        os.rename(tmp_filename, base_filename)
    except (OSError, IOError) as e:
        logging.info("Could not update statistic '%s': %s" % (name, e))
