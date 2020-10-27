from typing import Dict

import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import RealmPlayground, get_realm


class RealmPlaygroundTests(ZulipTestCase):
    def json_serialize(self, payload: Dict[str, str]) -> Dict[str, str]:
        payload["url_prefix"] = orjson.dumps(payload["url_prefix"]).decode()
        payload["pygments_language"] = orjson.dumps(payload["pygments_language"]).decode()
        return payload

    def test_create_one_playground_entry(self) -> None:
        iago = self.example_user("iago")

        payload = {
            "name": "Python playground",
            "pygments_language": "Python",
            "url_prefix": "https://python.example.com",
        }
        # Now send a POST request to the API endpoint.
        resp = self.api_post(iago, "/json/realm/playgrounds", self.json_serialize(payload))
        self.assert_json_success(resp)

        # Check if the actual object exists
        realm = get_realm("zulip")
        self.assertTrue(
            RealmPlayground.objects.filter(realm=realm, name="Python playground").exists()
        )

    def test_create_multiple_playgrounds_for_same_language(self) -> None:
        iago = self.example_user("iago")

        data = [
            {
                "name": "Python playground 1",
                "pygments_language": "Python",
                "url_prefix": "https://python.example.com",
            },
            {
                "name": "Python playground 2",
                "pygments_language": "Python",
                "url_prefix": "https://python2.example.com",
            },
        ]
        for payload in data:
            resp = self.api_post(iago, "/json/realm/playgrounds", self.json_serialize(payload))
            self.assert_json_success(resp)

        realm = get_realm("zulip")
        self.assertTrue(
            RealmPlayground.objects.filter(realm=realm, name="Python playground 1").exists()
        )
        self.assertTrue(
            RealmPlayground.objects.filter(realm=realm, name="Python playground 2").exists()
        )

    def test_invalid_params(self) -> None:
        iago = self.example_user("iago")

        payload = {
            "name": "Invalid URL",
            "pygments_language": "Python",
            "url_prefix": "https://invalid-url",
        }
        resp = self.api_post(iago, "/json/realm/playgrounds", self.json_serialize(payload))
        self.assert_json_error(resp, "url_prefix is not a URL")

        payload["url_prefix"] = "https://python.example.com"
        payload["pygments_language"] = "a$b$c"
        resp = self.api_post(iago, "/json/realm/playgrounds", self.json_serialize(payload))
        self.assert_json_error(resp, "Invalid characters in pygments language")

    def test_create_already_existing_playground(self) -> None:
        iago = self.example_user("iago")

        payload = {
            "name": "Python playground",
            "pygments_language": "Python",
            "url_prefix": "https://python.example.com",
        }
        serialized_payload = self.json_serialize(payload)
        resp = self.api_post(iago, "/json/realm/playgrounds", serialized_payload)
        self.assert_json_success(resp)

        resp = self.api_post(iago, "/json/realm/playgrounds", serialized_payload)
        self.assert_json_error(resp, "Realm playground with this Realm and Name already exists.")

    def test_not_realm_admin(self) -> None:
        hamlet = self.example_user("hamlet")

        resp = self.api_post(hamlet, "/json/realm/playgrounds")
        self.assert_json_error(resp, "Must be an organization administrator")
