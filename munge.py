import glob
import os
import re

"""
This is just a hacky script to set up a "spy"
decorator on various functions within the Zulip
app.
"""

# MODIFY THIS TO CHOOSE WHICH FILES TO SPY ON.
# (or you can just edit files manually)
FNS = 'zerver/lib/actions.py'

def fix_file(fn):
    if "spy.py" in fn:
        # don't spy on the spy!
        return

    with open(fn) as f:
        lines = f.readlines()

    with open(fn, 'w') as f:
        f.write("from zerver.lib.spy import spy\n")

        line_feeder = enumerate(lines)
        while True:
            try:
                i, line = next(line_feeder)

                s = line

                m = re.match("(\s*?)def ", line)
                if m:
                    indent = len(m.group(1))

                    f.write(indent * " " + "@spy\n")
                    f.write(line)

                    continue


                f.write(line)
            except StopIteration:
                break

def run():
    os.system('git checkout ' + FNS)

    for fn in glob.glob(FNS):
        fix_file(fn)

    # os.system('./tools/lint --only=prettier --fix frontend_tests/node_tests')
    os.system('git diff')

run()
