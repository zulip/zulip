from typing import Dict, Set

class SubscriberHandler:
    def __init__(self) -> None:
        self.stream_info = dict()  # type: Dict[int, Set[int]]

    def set_info(self,
                 stream_id: int,
                 users: Set[int]) -> None:
        self.stream_info[stream_id] = users

    def get_users(self,
                  stream_id: int) -> Set[int]:
        users = self.stream_info[stream_id]
        return users
