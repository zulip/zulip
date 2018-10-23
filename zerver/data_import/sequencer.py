from typing import Callable, Dict

'''
This module helps you set up a bunch
of sequences, similar to how database
sequences work.

You need to be a bit careful here, since
you're dealing with a big singleton, but
for data imports that's usually easy to
manage.  See hipchat.py for example usage.
'''

def _seq() -> Callable[[], int]:
    i = 0

    def next_one() -> int:
        nonlocal i
        i += 1
        return i

    return next_one

def sequencer() -> Callable[[str], int]:
    '''
        Use like this:

        NEXT_ID = sequencer()
        message_id = NEXT_ID('message')
    '''
    seq_dict = dict()  # type: Dict[str, Callable[[], int]]

    def next_one(name: str) -> int:
        if name not in seq_dict:
            seq_dict[name] = _seq()
        seq = seq_dict[name]
        return seq()

    return next_one

'''
NEXT_ID is a singleton used by an entire process, which is
almost always reasonable.  If you want to have two parallel
sequences, just use different `name` values.

This object gets created once and only once during the first
import of the file.
'''

NEXT_ID = sequencer()
