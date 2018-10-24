from typing import Any, Dict, Set

class SubscriberHandler:
    '''
    A note on ids here: we borrow Hipchat ids as Zulip
    ids during the conversion phase.  (They get re-mapped
    during import, but that doesn't concern use here.)

    So these are all synonymous:

        HipChat room_id == Zulip stream_id
        member ids = hipchat user ids = Zulip user_id
        owner id = hipchat user id = Zulip user_id

    In this class, when it's somewhat arbitrary whether
    to call something a "room" or a "stream", we use
    the Zulip naming.
    '''
    def __init__(self) -> None:
        self.stream_info = dict()  # type: Dict[int, Dict[str, Any]]

    def set_info(self,
                 stream_id: int,
                 owner: int,
                 members: Set[int]) -> None:
        # Our callers are basically giving us
        # data straight out of rooms.json.
        self.stream_info[stream_id] = dict(
            owner=owner,
            members=members,
        )

    def get_users(self,
                  stream_id: int) -> Set[int]:
        info = self.stream_info[stream_id]
        users = info['members'] | {info['owner']}
        return users
