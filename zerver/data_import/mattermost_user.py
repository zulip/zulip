from typing import Any, Dict, List

class UserHandler:
    '''
    Our UserHandler class is a glorified wrapper
    around the data that eventually goes into
    zerver_userprofile.

    The class helps us do things like map ids
    to names for mentions.
    '''
    def __init__(self) -> None:
        self.id_to_user_map = dict()  # type: Dict[int, Dict[str, Any]]

    def add_user(self, user: Dict[str, Any]) -> None:
        user_id = user['id']
        self.id_to_user_map[user_id] = user

    def get_user(self, user_id: int) -> Dict[str, Any]:
        user = self.id_to_user_map[user_id]
        return user

    def get_all_users(self) -> List[Dict[str, Any]]:
        users = list(self.id_to_user_map.values())
        return users
