from typing import Any, Dict, List

from django.utils.timezone import now as timezone_now

from zerver.data_import.import_util import (
    build_user_profile,
)

class UserHandler:
    '''
    Our UserHandler class is a glorified wrapper
    around the data that eventually goes into
    zerver_userprofile.

    The class helps us do things like map ids
    to names for mentions.

    We also sometimes need to build mirror
    users on the fly.
    '''
    def __init__(self) -> None:
        self.id_to_user_map = dict()  # type: Dict[int, Dict[str, Any]]
        self.name_to_mirror_user_map = dict()  # type: Dict[str, Dict[str, Any]]
        self.mirror_user_id = 1

    def add_user(self, user: Dict[str, Any]) -> None:
        user_id = user['id']
        self.id_to_user_map[user_id] = user

    def get_user(self, user_id: int) -> Dict[str, Any]:
        user = self.id_to_user_map[user_id]
        return user

    def get_mirror_user(self,
                        realm_id: int,
                        name: str) -> Dict[str, Any]:
        if name in self.name_to_mirror_user_map:
            user = self.name_to_mirror_user_map[name]
            return user

        user_id = self._new_mirror_user_id()
        short_name = name
        full_name = name
        email = 'mirror-{user_id}@example.com'.format(user_id=user_id)
        delivery_email = email
        avatar_source = 'G'
        date_joined = int(timezone_now().timestamp())
        timezone = 'UTC'

        user = build_user_profile(
            avatar_source=avatar_source,
            date_joined=date_joined,
            delivery_email=delivery_email,
            email=email,
            full_name=full_name,
            id=user_id,
            is_active=False,
            is_realm_admin=False,
            is_guest=False,
            is_mirror_dummy=True,
            realm_id=realm_id,
            short_name=short_name,
            timezone=timezone,
        )

        self.name_to_mirror_user_map[name] = user
        return user

    def _new_mirror_user_id(self) -> int:
        next_id = self.mirror_user_id
        while next_id in self.id_to_user_map:
            next_id += 1
        self.mirror_user_id = next_id + 1
        return next_id

    def get_normal_users(self) -> List[Dict[str, Any]]:
        users = list(self.id_to_user_map.values())
        return users

    def get_all_users(self) -> List[Dict[str, Any]]:
        normal_users = self.get_normal_users()
        mirror_users = list(self.name_to_mirror_user_map.values())
        all_users = normal_users + mirror_users
        return all_users
