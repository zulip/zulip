from typing import Any

from social_core.backends.oauth import BaseOAuth2


class DiscordOAuth2(BaseOAuth2):
    name = "discord"
    AUTHORIZATION_URL = "https://discord.com/api/oauth2/authorize"
    ACCESS_TOKEN_URL = "https://discord.com/api/oauth2/token"
    USER_DATA_URL = "https://discord.com/api/users/@me"

    def get_user_details(self, response: dict[str, Any]) -> dict[str, Any]:
        return {
            "username": response.get("username"),
            "email": response.get("email"),
            "fullname": response.get("global_name") or response.get("username"),
        }

    def user_data(self, access_token: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.get_json(
            self.USER_DATA_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
