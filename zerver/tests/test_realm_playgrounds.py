from zerver.actions.realm_playgrounds import check_add_realm_playground
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import RealmPlayground, get_realm


class RealmPlaygroundTests(ZulipTestCase):
    def test_create_one_playground_entry(self) -> None:
        iago = self.example_user("iago")

        payload = {
            "name": "Python playground",
            "pygments_language": "Python",
            "url_template": "https://python.example.com{code}",
        }
        # Now send a POST request to the API endpoint.
        resp = self.api_post(iago, "/api/v1/realm/playgrounds", payload)
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
                "url_template": "https://python.example.com{code}",
            },
            {
                "name": "Python playground 2",
                "pygments_language": "Python",
                "url_template": "https://python2.example.com{code}",
            },
        ]
        for payload in data:
            resp = self.api_post(iago, "/api/v1/realm/playgrounds", payload)
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
            "name": "Invalid characters in pygments language",
            "pygments_language": "a$b$c",
            "url_template": "https://template.com{code}",
        }
        resp = self.api_post(iago, "/api/v1/realm/playgrounds", payload)
        self.assert_json_error(resp, "Invalid characters in pygments language")

        payload = {
            "name": "Template with an unexpected variable",
            "pygments_language": "Python",
            "url_template": "https://template.com{?test,code}",
        }
        resp = self.api_post(iago, "/api/v1/realm/playgrounds", payload)
        self.assert_json_error(
            resp, '"code" should be the only variable present in the URL template'
        )

        payload = {
            "name": "Invalid URL template",
            "pygments_language": "Python",
            "url_template": "https://template.com?test={test",
        }
        resp = self.api_post(iago, "/api/v1/realm/playgrounds", payload)
        self.assert_json_error(resp, "Invalid URL template.")

        payload = {
            "name": "Template without the required variable",
            "pygments_language": "Python",
            "url_template": "https://template.com{?test}",
        }
        resp = self.api_post(iago, "/api/v1/realm/playgrounds", payload)
        self.assert_json_error(resp, 'Missing the required variable "code" in the URL template')

    def test_create_already_existing_playground(self) -> None:
        iago = self.example_user("iago")

        payload = {
            "name": "Python playground",
            "pygments_language": "Python",
            "url_template": "https://python.example.com{code}",
        }
        resp = self.api_post(iago, "/api/v1/realm/playgrounds", payload)
        self.assert_json_success(resp)

        resp = self.api_post(iago, "/api/v1/realm/playgrounds", payload)
        self.assert_json_error(
            resp, "Realm playground with this Realm, Pygments language and Name already exists."
        )

    def test_not_realm_admin(self) -> None:
        hamlet = self.example_user("hamlet")

        resp = self.api_post(hamlet, "/api/v1/realm/playgrounds")
        self.assert_json_error(resp, "Must be an organization administrator")

        resp = self.api_delete(hamlet, "/api/v1/realm/playgrounds/1")
        self.assert_json_error(resp, "Must be an organization administrator")

    def test_delete_realm_playground(self) -> None:
        iago = self.example_user("iago")
        realm = get_realm("zulip")

        playground_id = check_add_realm_playground(
            realm,
            acting_user=iago,
            name="Python playground",
            pygments_language="Python",
            url_template="https://python.example.com{code}",
        )
        self.assertTrue(RealmPlayground.objects.filter(name="Python playground").exists())

        result = self.api_delete(iago, f"/api/v1/realm/playgrounds/{playground_id + 1}")
        self.assert_json_error(result, "Invalid playground")

        result = self.api_delete(iago, f"/api/v1/realm/playgrounds/{playground_id}")
        self.assert_json_success(result)
        self.assertFalse(RealmPlayground.objects.filter(name="Python").exists())
