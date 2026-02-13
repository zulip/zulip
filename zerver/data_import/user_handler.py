from typing import Any

from zerver.data_import.import_util import validate_user_emails_for_import


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
        self.mattermost_user_id_to_zulip_recipient_id: dict[str, int] = {}

    def add_user(self, user: dict[str, Any]) -> None:
        user_id = user["id"]
        self.id_to_user_map[user_id] = user

    def add_mattermost_user_id_to_zulip_recipient_id(
        self, mattermost_user_id: str, zulip_recipient_id: int
    ) -> None:
        # TODO: Maybe combine this with self.add_user() once when we do a refactor for
        # the Rocketchat importer to use this function.
        self.mattermost_user_id_to_zulip_recipient_id[mattermost_user_id] = zulip_recipient_id

    def get_user(self, user_id: int) -> dict[str, Any]:
        user = self.id_to_user_map[user_id]
        return user

    def get_all_users(self) -> list[dict[str, Any]]:
        users = list(self.id_to_user_map.values())
        return users

    def get_zulip_recipient_id(self, mattermost_user_id: str) -> int | None:
        return self.mattermost_user_id_to_zulip_recipient_id.get(mattermost_user_id)

    def validate_user_emails(self) -> None:
        all_users = self.get_all_users()
        validate_user_emails_for_import([user["delivery_email"] for user in all_users])
