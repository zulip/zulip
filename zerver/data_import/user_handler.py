from typing import Any


class UserHandler:
    """
    Our UserHandler class is a glorified wrapper
    around the data that eventually goes into
    zerver_userprofile.

    The class helps us do things like map ids
    to names for mentions.
    """

    def __init__(self) -> None:
        self.id_to_user_map: dict[int, dict[str, Any]] = {}

    def add_user(self, user: dict[str, Any]) -> None:
        user_id = user["id"]
        self.id_to_user_map[user_id] = user

    def get_user(self, user_id: int) -> dict[str, Any]:
        user = self.id_to_user_map[user_id]
        return user

    def get_all_users(self) -> list[dict[str, Any]]:
        users = list(self.id_to_user_map.values())
        return users
