import copy
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, TypedDict
from unittest import mock

import orjson
from django.conf import settings
from typing_extensions import override

from zerver.actions.user_groups import check_add_user_group, do_deactivate_user_group
from zerver.actions.user_settings import do_change_full_name
from zerver.lib.stream_subscription import get_subscribed_stream_ids_for_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_user_group_direct_member_ids
from zerver.models import UserProfile
from zerver.models.groups import NamedUserGroup
from zerver.models.realms import get_realm

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class SCIMHeadersDict(TypedDict):
    HTTP_AUTHORIZATION: str


class SCIMTestCase(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.realm = get_realm("zulip")

    def scim_headers(self) -> SCIMHeadersDict:
        return {"HTTP_AUTHORIZATION": f"Bearer {settings.SCIM_CONFIG['zulip']['bearer_token']}"}

    def generate_user_schema(self, user_profile: UserProfile) -> dict[str, Any]:
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "id": str(user_profile.id),
            "userName": user_profile.delivery_email,
            "name": {"formatted": user_profile.full_name},
            "displayName": user_profile.full_name,
            "role": UserProfile.ROLE_ID_TO_API_NAME[user_profile.role],
            "active": True,
            "meta": {
                "resourceType": "User",
                "created": user_profile.date_joined.isoformat(),
                "lastModified": user_profile.date_joined.isoformat(),
                "location": f"http://zulip.testserver/scim/v2/Users/{user_profile.id}",
            },
        }

    def assert_uniqueness_error(self, result: "TestHttpResponse", extra_message: str) -> None:
        self.assertEqual(result.status_code, 409)
        output_data = orjson.loads(result.content)

        expected_response_schema = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
            "detail": f"Email address already in use: {extra_message}",
            "status": 409,
            "scimType": "uniqueness",
        }
        self.assertEqual(output_data, expected_response_schema)

    @contextmanager
    def mock_name_formatted_included(self, value: bool) -> Iterator[None]:
        config_dict = copy.deepcopy(settings.SCIM_CONFIG)
        config_dict["zulip"]["name_formatted_included"] = value
        with self.settings(SCIM_CONFIG=config_dict):
            yield


class TestNonSCIMAPIAccess(SCIMTestCase):
    def test_scim_client_cant_access_different_apis(self) -> None:
        """
        Verify that the SCIM client credentials can't be used to get
        authenticated for non-SCIM API.
        """
        hamlet = self.example_user("hamlet")

        # First verify validate_scim_bearer_token doesn't even get called,
        # as verification of SCIM credentials shouldn't even be attempted,
        # because we're not querying a SCIM endpoint.
        with mock.patch("zerver.middleware.validate_scim_bearer_token", return_value=None) as m:
            result = self.client_get(f"/api/v1/users/{hamlet.id}", {}, **self.scim_headers())

        # The SCIM format of the Authorization header (bearer token) is rejected as a bad request
        # by our regular API authentication logic.
        self.assert_json_error(result, "This endpoint requires HTTP basic authentication.", 400)
        m.assert_not_called()

        # Now simply test end-to-end that access gets denied, without any mocking
        # interfering with the process.
        result = self.client_get(f"/api/v1/users/{hamlet.id}", {}, **self.scim_headers())
        self.assert_json_error(result, "This endpoint requires HTTP basic authentication.", 400)


class TestExceptionDetailsNotRevealedToClient(SCIMTestCase):
    def test_exception_details_not_revealed_to_client(self) -> None:
        """
        Verify that, unlike in default django-scim2 behavior, details of an exception
        are not revealed in the HttpResponse.
        """
        with (
            mock.patch(
                "zerver.lib.scim.ZulipSCIMUser.to_dict", side_effect=Exception("test exception")
            ),
            self.assertLogs("django_scim.views", "ERROR") as mock_scim_logger,
            self.assertLogs("django.request", "ERROR") as mock_request_logger,
        ):
            result = self.client_get("/scim/v2/Users", {}, **self.scim_headers())
            # Only a generic error message is returned:
            self.assertEqual(
                orjson.loads(result.content),
                {
                    "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                    "detail": "Exception occurred while processing the SCIM request",
                    "status": 500,
                },
            )
            # Details of the exception still get internally logged as expected:
            self.assertIn("test exception", mock_scim_logger.output[0])
            self.assertIn("Internal Server Error: /scim/v2/Users", mock_request_logger.output[0])


class TestSCIMUser(SCIMTestCase):
    def test_bad_authentication(self) -> None:
        hamlet = self.example_user("hamlet")

        result = self.client_get(f"/scim/v2/Users/{hamlet.id}", {})
        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.headers["WWW-Authenticate"], 'Basic realm="django-scim2"')

        result = self.client_get(
            f"/scim/v2/Users/{hamlet.id}", {"HTTP_AUTHORIZATION": "Bearer wrong"}
        )
        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.headers["WWW-Authenticate"], 'Basic realm="django-scim2"')

    def test_get_by_id(self) -> None:
        hamlet = self.example_user("hamlet")
        expected_response_schema = self.generate_user_schema(hamlet)

        result = self.client_get(f"/scim/v2/Users/{hamlet.id}", {}, **self.scim_headers())

        self.assertEqual(result.status_code, 200)
        output_data = orjson.loads(result.content)
        self.assertEqual(output_data, expected_response_schema)

    def test_get_basic_filter_by_username(self) -> None:
        hamlet = self.example_user("hamlet")

        expected_response_schema = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": 1,
            "itemsPerPage": 50,
            "startIndex": 1,
            "Resources": [self.generate_user_schema(hamlet)],
        }

        result = self.client_get(
            f'/scim/v2/Users?filter=userName eq "{hamlet.delivery_email}"',
            {},
            **self.scim_headers(),
        )
        self.assertEqual(result.status_code, 200)
        output_data = orjson.loads(result.content)
        self.assertEqual(output_data, expected_response_schema)

        # Now we verify the filter feature doesn't allow access to users
        # on different subdomains.
        different_realm_user = self.mit_user("starnine")
        self.assertNotEqual(different_realm_user.realm_id, hamlet.realm_id)

        result = self.client_get(
            f'/scim/v2/Users?filter=userName eq "{different_realm_user.delivery_email}"',
            {},
            **self.scim_headers(),
        )
        self.assertEqual(result.status_code, 200)
        output_data = orjson.loads(result.content)

        expected_empty_results_response_schema = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": 0,
            "itemsPerPage": 50,
            "startIndex": 1,
            "Resources": [],
        }

        self.assertEqual(output_data, expected_empty_results_response_schema)

    def test_get_basic_filter_by_username_case_insensitive(self) -> None:
        """
        Verifies that the "userName eq XXXX" syntax is case-insensitive.
        """

        hamlet = self.example_user("hamlet")

        # The assumption for the test to make sense is that these two are not the same:
        self.assertNotEqual(hamlet.delivery_email.upper(), hamlet.delivery_email)

        expected_response_schema = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": 1,
            "itemsPerPage": 50,
            "startIndex": 1,
            "Resources": [self.generate_user_schema(hamlet)],
        }

        result = self.client_get(
            f'/scim/v2/Users?filter=userName eq "{hamlet.delivery_email.upper()}"',
            {},
            **self.scim_headers(),
        )
        self.assertEqual(result.status_code, 200)
        output_data = orjson.loads(result.content)
        self.assertEqual(output_data, expected_response_schema)

    def test_get_all_with_pagination(self) -> None:
        realm = get_realm("zulip")

        result_all = self.client_get("/scim/v2/Users", {}, **self.scim_headers())
        self.assertEqual(result_all.status_code, 200)
        output_data_all = orjson.loads(result_all.content)

        expected_response_schema = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": UserProfile.objects.filter(realm=realm, is_bot=False).count(),
            "itemsPerPage": 50,
            "startIndex": 1,
            "Resources": [
                self.generate_user_schema(user_profile)
                for user_profile in UserProfile.objects.filter(realm=realm, is_bot=False).order_by(
                    "id"
                )
            ],
        }

        self.assertEqual(output_data_all, expected_response_schema)

        # Test pagination works, as defined in https://datatracker.ietf.org/doc/html/rfc7644#section-3.4.2.4
        result_offset_limited = self.client_get(
            "/scim/v2/Users?startIndex=4&count=3", {}, **self.scim_headers()
        )
        self.assertEqual(result_offset_limited.status_code, 200)
        output_data_offset_limited = orjson.loads(result_offset_limited.content)
        self.assertEqual(output_data_offset_limited["itemsPerPage"], 3)
        self.assertEqual(output_data_offset_limited["startIndex"], 4)
        self.assertEqual(
            output_data_offset_limited["totalResults"], output_data_all["totalResults"]
        )
        self.assert_length(output_data_offset_limited["Resources"], 3)

        self.assertEqual(output_data_offset_limited["Resources"], output_data_all["Resources"][3:6])

    def test_get_user_with_no_name_formatted_included_config(self) -> None:
        """
        Some clients don't support name.formatted and rely and name.givenName and name.familyName.
        We have the name_formatted_included configuration option for it for supporting that
        behavior. Here we test the return dict representation of the User has the appropriate
        format and values.
        """
        hamlet = self.example_user("hamlet")
        do_change_full_name(hamlet, "Firstname Lastname", acting_user=None)
        expected_response_schema = self.generate_user_schema(hamlet)
        expected_response_schema["name"] = {"givenName": "Firstname", "familyName": "Lastname"}

        with self.mock_name_formatted_included(False):
            result = self.client_get(f"/scim/v2/Users/{hamlet.id}", {}, **self.scim_headers())

        self.assertEqual(result.status_code, 200)
        output_data = orjson.loads(result.content)
        self.assertEqual(output_data, expected_response_schema)

        do_change_full_name(hamlet, "Firstnameonly", acting_user=None)
        expected_response_schema = self.generate_user_schema(hamlet)
        expected_response_schema["name"] = {"givenName": "Firstnameonly", "familyName": ""}

        with self.mock_name_formatted_included(False):
            result = self.client_get(f"/scim/v2/Users/{hamlet.id}", {}, **self.scim_headers())

        self.assertEqual(result.status_code, 200)
        output_data = orjson.loads(result.content)
        self.assertEqual(output_data, expected_response_schema)

    def test_search_users(self) -> None:
        """
        Tests a basic .search POST query:
        https://datatracker.ietf.org/doc/html/rfc7644#section-3.4.3
        """
        realm = get_realm("zulip")

        # A payload to find all users whose email ends with @zulip.com
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:SearchRequest"],
            "filter": 'userName ew "@zulip.com"',
        }
        result = self.client_post(
            "/scim/v2/Users/.search",
            payload,
            content_type="application/json",
            **self.scim_headers(),
        )
        self.assertEqual(result.status_code, 200)
        output_data = orjson.loads(result.content)

        user_query = UserProfile.objects.filter(
            realm=realm, is_bot=False, delivery_email__endswith="@zulip.com"
        )
        expected_response_schema = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": user_query.count(),
            "itemsPerPage": 50,
            "startIndex": 1,
            "Resources": [
                self.generate_user_schema(user_profile)
                for user_profile in UserProfile.objects.filter(realm=realm, is_bot=False).order_by(
                    "id"
                )
            ],
        }

        self.assertEqual(output_data, expected_response_schema)

    def test_post(self) -> None:
        # A payload for creating a new user with the specified account details.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "newuser@zulip.com",
            "name": {"formatted": "New User", "givenName": "New", "familyName": "User"},
            "active": True,
        }

        original_user_count = UserProfile.objects.count()
        result = self.client_post(
            "/scim/v2/Users", payload, content_type="application/json", **self.scim_headers()
        )

        self.assertEqual(result.status_code, 201)
        output_data = orjson.loads(result.content)

        new_user_count = UserProfile.objects.count()
        self.assertEqual(new_user_count, original_user_count + 1)

        new_user = UserProfile.objects.last()
        assert new_user is not None
        self.assertEqual(new_user.delivery_email, "newuser@zulip.com")
        self.assertEqual(new_user.full_name, "New User")
        self.assertEqual(new_user.role, UserProfile.ROLE_MEMBER)

        expected_response_schema = self.generate_user_schema(new_user)
        self.assertEqual(output_data, expected_response_schema)

    def test_post_with_role(self) -> None:
        # A payload for creating a new user with the specified account details, including
        # specifying the role.

        # Start with a payload with an invalid role value, to test error handling.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "newuser@zulip.com",
            "name": {"formatted": "New User", "givenName": "New", "familyName": "User"},
            "active": True,
            "role": "wrongrole",
        }

        result = self.client_post(
            "/scim/v2/Users", payload, content_type="application/json", **self.scim_headers()
        )
        self.assertEqual(
            orjson.loads(result.content),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": "Invalid role: wrongrole. Valid values are: ['owner', 'administrator', 'moderator', 'member', 'guest']",
                "status": 400,
            },
        )

        # Now fix the role to make a valid request to create an administrator and proceed.
        payload["role"] = "administrator"
        result = self.client_post(
            "/scim/v2/Users", payload, content_type="application/json", **self.scim_headers()
        )

        self.assertEqual(result.status_code, 201)
        output_data = orjson.loads(result.content)

        new_user = UserProfile.objects.last()
        assert new_user is not None
        self.assertEqual(new_user.delivery_email, "newuser@zulip.com")
        self.assertEqual(new_user.role, UserProfile.ROLE_REALM_ADMINISTRATOR)

        expected_response_schema = self.generate_user_schema(new_user)
        self.assertEqual(output_data, expected_response_schema)

    def test_post_create_guest_user_without_streams(self) -> None:
        @contextmanager
        def mock_create_guests_without_streams() -> Iterator[None]:
            config_dict = copy.deepcopy(settings.SCIM_CONFIG)
            config_dict["zulip"]["create_guests_without_streams"] = True
            with self.settings(SCIM_CONFIG=config_dict):
                yield

        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "newuser@zulip.com",
            "name": {"formatted": "New User", "givenName": "New", "familyName": "User"},
            "active": True,
            "role": "guest",
        }
        with mock_create_guests_without_streams():
            result = self.client_post(
                "/scim/v2/Users", payload, content_type="application/json", **self.scim_headers()
            )

        self.assertEqual(result.status_code, 201)
        output_data = orjson.loads(result.content)

        new_user = UserProfile.objects.last()
        assert new_user is not None
        self.assertEqual(new_user.delivery_email, "newuser@zulip.com")
        self.assertEqual(new_user.role, UserProfile.ROLE_GUEST)

        expected_response_schema = self.generate_user_schema(new_user)
        self.assertEqual(output_data, expected_response_schema)

        self.assertEqual(list(get_subscribed_stream_ids_for_user(new_user)), [])

    def test_post_with_no_name_formatted_included_config(self) -> None:
        # A payload for creating a new user with the specified account details.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "newuser@zulip.com",
            "name": {"givenName": "New", "familyName": "User"},
            "active": True,
        }

        original_user_count = UserProfile.objects.count()
        with self.mock_name_formatted_included(False):
            result = self.client_post(
                "/scim/v2/Users", payload, content_type="application/json", **self.scim_headers()
            )

        self.assertEqual(result.status_code, 201)
        output_data = orjson.loads(result.content)

        new_user_count = UserProfile.objects.count()
        self.assertEqual(new_user_count, original_user_count + 1)

        new_user = UserProfile.objects.last()
        assert new_user is not None
        self.assertEqual(new_user.delivery_email, "newuser@zulip.com")
        self.assertEqual(new_user.full_name, "New User")

        expected_response_schema = self.generate_user_schema(new_user)
        expected_response_schema["name"] = {"givenName": "New", "familyName": "User"}
        self.assertEqual(output_data, expected_response_schema)

    def test_post_email_exists(self) -> None:
        hamlet = self.example_user("hamlet")
        # A payload for creating a new user with an email that already exists. Thus
        # this should fail.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": hamlet.delivery_email,
            "name": {"formatted": "New User", "givenName": "New", "familyName": "User"},
            "active": True,
        }

        result = self.client_post(
            "/scim/v2/Users", payload, content_type="application/json", **self.scim_headers()
        )
        self.assert_uniqueness_error(result, f"['{hamlet.delivery_email} already has an account']")

    def test_post_name_attribute_missing(self) -> None:
        # A payload for creating a new user without a name, which should make this request fail.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "newuser@zulip.com",
            "active": True,
        }

        result = self.client_post(
            "/scim/v2/Users", payload, content_type="application/json", **self.scim_headers()
        )
        self.assertEqual(
            orjson.loads(result.content),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": "Must specify name.formatted, name.givenName or name.familyName when creating a new user",
                "status": 400,
            },
        )

    def test_post_active_set_to_false(self) -> None:
        # A payload for creating a new user with is_active=False, which is an invalid operation.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "newuser@zulip.com",
            "name": {"formatted": "New User", "givenName": "New", "familyName": "User"},
            "active": False,
        }

        result = self.client_post(
            "/scim/v2/Users", payload, content_type="application/json", **self.scim_headers()
        )
        self.assertEqual(
            orjson.loads(result.content),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": "New user must have active=True",
                "status": 400,
            },
        )

    def test_post_email_domain_not_allow(self) -> None:
        realm = get_realm("zulip")
        realm.emails_restricted_to_domains = True
        realm.save(update_fields=["emails_restricted_to_domains"])

        # A payload for creating a new user with the specified details.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "newuser@acme.com",
            "name": {"formatted": "New User", "givenName": "New", "familyName": "User"},
            "active": True,
        }

        result = self.client_post(
            "/scim/v2/Users", payload, content_type="application/json", **self.scim_headers()
        )
        self.assertEqual(
            orjson.loads(result.content),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": "This email domain isn't allowed in this organization.",
                "status": 400,
            },
        )

    def test_post_to_try_creating_new_user_on_different_subdomain(self) -> None:
        # A payload for creating a new user with the specified details.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "newuser@acme.com",
            "name": {"formatted": "New User", "givenName": "New", "familyName": "User"},
            "active": True,
        }

        # Now we make the SCIM request to a different subdomain than our credentials
        # are configured for. Unauthorized is the expected response.
        result = self.client_post(
            "/scim/v2/Users",
            payload,
            content_type="application/json",
            subdomain="lear",
            **self.scim_headers(),
        )
        self.assertEqual(result.status_code, 401)

    def test_delete(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.client_delete(f"/scim/v2/Users/{hamlet.id}", {}, **self.scim_headers())

        expected_response_schema = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
            "detail": 'DELETE operation not supported. Use PUT or PATCH to modify the "active" attribute instead.',
            "status": 400,
        }

        self.assertEqual(result.status_code, 400)
        output_data = orjson.loads(result.content)
        self.assertEqual(output_data, expected_response_schema)

    def test_put_change_email_and_name(self) -> None:
        hamlet = self.example_user("hamlet")
        # PUT replaces all specified attributes of the user. Thus,
        # this payload will replace hamlet's account details with the new ones,
        # as specified.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "id": hamlet.id,
            "userName": "bjensen@zulip.com",
            "name": {
                "formatted": "Ms. Barbara J Jensen III",
                "familyName": "Jensen",
                "givenName": "Barbara",
                "middleName": "Jane",
            },
        }
        result = self.json_put(f"/scim/v2/Users/{hamlet.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        hamlet.refresh_from_db()
        self.assertEqual(hamlet.delivery_email, "bjensen@zulip.com")
        self.assertEqual(hamlet.full_name, "Ms. Barbara J Jensen III")

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_user_schema(hamlet)
        self.assertEqual(output_data, expected_response_schema)

    def test_put_change_name_only(self) -> None:
        hamlet = self.example_user("hamlet")
        hamlet_email = hamlet.delivery_email
        # This payload specified hamlet's current email to not change this attribute,
        # and only alters the name.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "id": hamlet.id,
            "userName": hamlet_email,
            "name": {
                "formatted": "Ms. Barbara J Jensen III",
                "familyName": "Jensen",
                "givenName": "Barbara",
                "middleName": "Jane",
            },
        }
        result = self.json_put(f"/scim/v2/Users/{hamlet.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        hamlet.refresh_from_db()
        self.assertEqual(hamlet.delivery_email, hamlet_email)
        self.assertEqual(hamlet.full_name, "Ms. Barbara J Jensen III")

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_user_schema(hamlet)
        self.assertEqual(output_data, expected_response_schema)

    def test_put_email_exists(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        # This payload will attempt to change hamlet's email to cordelia's email.
        # That would violate email uniqueness of course, so should fail.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "id": hamlet.id,
            "userName": cordelia.delivery_email,
            "name": {
                "formatted": "Ms. Barbara J Jensen III",
                "familyName": "Jensen",
                "givenName": "Barbara",
                "middleName": "Jane",
            },
        }
        result = self.json_put(f"/scim/v2/Users/{hamlet.id}", payload, **self.scim_headers())
        self.assert_uniqueness_error(
            result, f"['{cordelia.delivery_email} already has an account']"
        )

    def test_put_change_user_role(self) -> None:
        hamlet = self.example_user("hamlet")
        hamlet_email = hamlet.delivery_email
        self.assertEqual(hamlet.role, UserProfile.ROLE_MEMBER)

        # This payload changes hamlet's role to administrator.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "id": hamlet.id,
            "userName": hamlet_email,
            "role": "administrator",
        }
        result = self.json_put(f"/scim/v2/Users/{hamlet.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        hamlet.refresh_from_db()
        self.assertEqual(hamlet.role, UserProfile.ROLE_REALM_ADMINISTRATOR)

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_user_schema(hamlet)
        self.assertEqual(output_data, expected_response_schema)

    def test_put_deactivate_reactivate_user(self) -> None:
        hamlet = self.example_user("hamlet")
        # This payload flips the active attribute to deactivate the user.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "id": hamlet.id,
            "userName": hamlet.delivery_email,
            "active": False,
        }
        result = self.json_put(f"/scim/v2/Users/{hamlet.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        hamlet.refresh_from_db()
        self.assertEqual(hamlet.is_active, False)

        # We modify the active attribute in the payload to cause reactivation of the user.
        payload["active"] = True
        result = self.json_put(f"/scim/v2/Users/{hamlet.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        hamlet.refresh_from_db()
        self.assertEqual(hamlet.is_active, True)

    def test_patch_with_path(self) -> None:
        hamlet = self.example_user("hamlet")
        # Payload for a PATCH request to change the user's email to the specified value.
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "path": "userName", "value": "hamlet_new@zulip.com"}],
        }

        result = self.json_patch(f"/scim/v2/Users/{hamlet.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        hamlet.refresh_from_db()
        self.assertEqual(hamlet.delivery_email, "hamlet_new@zulip.com")

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_user_schema(hamlet)
        self.assertEqual(output_data, expected_response_schema)

        # Multiple operations:
        # This payload changes the user's email and name to the specified values.
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {"op": "replace", "path": "userName", "value": "hamlet_new2@zulip.com"},
                {"op": "replace", "path": "name.formatted", "value": "New Name"},
            ],
        }
        result = self.json_patch(f"/scim/v2/Users/{hamlet.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        hamlet.refresh_from_db()
        self.assertEqual(hamlet.full_name, "New Name")
        self.assertEqual(hamlet.delivery_email, "hamlet_new2@zulip.com")

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_user_schema(hamlet)
        self.assertEqual(output_data, expected_response_schema)

    def test_patch_without_path(self) -> None:
        """
        PATCH requests can also specify Operations in a different form,
        without specifying the "path" op attribute and instead specifying
        the user attribute to modify in the "value" dict.
        """

        hamlet = self.example_user("hamlet")
        # This payload changes the user's email to the specified value.
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "value": {"userName": "hamlet_new@zulip.com"}}],
        }

        result = self.json_patch(f"/scim/v2/Users/{hamlet.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        hamlet.refresh_from_db()
        self.assertEqual(hamlet.delivery_email, "hamlet_new@zulip.com")

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_user_schema(hamlet)
        self.assertEqual(output_data, expected_response_schema)

    def test_patch_change_user_role(self) -> None:
        hamlet = self.example_user("hamlet")
        # Payload for a PATCH request to change hamlet's role to administrator.
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "path": "role", "value": "administrator"}],
        }

        result = self.json_patch(f"/scim/v2/Users/{hamlet.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        hamlet.refresh_from_db()
        self.assertEqual(hamlet.role, UserProfile.ROLE_REALM_ADMINISTRATOR)

    def test_patch_deactivate_reactivate_user(self) -> None:
        hamlet = self.example_user("hamlet")
        # Payload for a PATCH request to deactivate the user.
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "path": "active", "value": False}],
        }

        result = self.json_patch(f"/scim/v2/Users/{hamlet.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        hamlet.refresh_from_db()
        self.assertEqual(hamlet.is_active, False)

        # Payload for a PATCH request to reactivate the user.
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "path": "active", "value": True}],
        }
        result = self.json_patch(f"/scim/v2/Users/{hamlet.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)
        hamlet.refresh_from_db()
        self.assertEqual(hamlet.is_active, True)

    def test_patch_unsupported_attribute(self) -> None:
        hamlet = self.example_user("hamlet")
        # Payload for a PATCH request to change the middle name of the user - which is not supported.
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "path": "name.middleName", "value": "John"}],
        }

        with self.assertLogs("django.request", "ERROR") as m:
            result = self.json_patch(f"/scim/v2/Users/{hamlet.id}", payload, **self.scim_headers())
            self.assertEqual(
                orjson.loads(result.content),
                {
                    "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                    "detail": "Not Implemented",
                    "status": 501,
                },
            )
            self.assertEqual(
                m.output, [f"ERROR:django.request:Not Implemented: /scim/v2/Users/{hamlet.id}"]
            )

    def test_scim_client_requester_for_logs(self) -> None:
        hamlet = self.example_user("hamlet")
        with self.assertLogs("zulip.requests", level="INFO") as m:
            result = self.client_get(f"/scim/v2/Users/{hamlet.id}", {}, **self.scim_headers())
        self.assertIn(
            f"scim-client:{settings.SCIM_CONFIG['zulip']['scim_client_name']}:realm:{hamlet.realm.id}",
            m.output[0],
        )
        self.assertEqual(result.status_code, 200)


class TestSCIMGroup(SCIMTestCase):
    """
    SCIM groups aren't implemented yet. An implementation will modify this class
    to actually test desired behavior.
    """

    def generate_group_schema(self, user_group: NamedUserGroup) -> dict[str, Any]:
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "id": str(user_group.id),
            "displayName": user_group.name,
            "members": [
                {
                    "value": str(user_profile.id),
                    "$ref": f"http://zulip.testserver/scim/v2/Users/{user_profile.id}",
                    "display": user_profile.full_name,
                    "type": "User",
                }
                for user_profile in UserProfile.objects.filter(
                    id__in=get_user_group_direct_member_ids(user_group), is_bot=False
                ).order_by("id")
            ],
            "meta": {
                "resourceType": "Group",
                "location": f"http://zulip.testserver/scim/v2/Groups/{user_group.id}",
            },
        }

    def test_get_by_id(self) -> None:
        realm = get_realm("zulip")
        desdemona = self.example_user("desdemona")
        hamlet = self.example_user("hamlet")
        bot = self.create_test_bot("whatever", hamlet)

        # We include a bot in the group memberships to verify that bots are ignored.
        test_group = check_add_user_group(realm, "Test group", [hamlet, bot], acting_user=desdemona)

        expected_data = self.generate_group_schema(test_group)
        result = self.client_get(f"/scim/v2/Groups/{test_group.id}", {}, **self.scim_headers())

        self.assertEqual(result.status_code, 200)

        output_data = orjson.loads(result.content)
        self.assertEqual(output_data, expected_data)

        member_ids = [int(user_dict["value"]) for user_dict in output_data["members"]]
        self.assertIn(hamlet.id, member_ids)
        self.assertNotIn(bot.id, member_ids)

    def test_get_basic_filter_by_display_name(self) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        desdemona = self.example_user("desdemona")
        test_group = check_add_user_group(realm, "Test group", [hamlet], acting_user=desdemona)

        expected_response_schema = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": 1,
            "itemsPerPage": 50,
            "startIndex": 1,
            "Resources": [self.generate_group_schema(test_group)],
        }

        result = self.client_get(
            f'/scim/v2/Groups?filter=displayName eq "{test_group.name}"',
            {},
            **self.scim_headers(),
        )
        self.assertEqual(result.status_code, 200)

        output_data = orjson.loads(result.content)
        self.assertEqual(output_data, expected_response_schema)

        # Deactivated groups are invisible to SCIM.
        do_deactivate_user_group(test_group, acting_user=None)

        expected_response_schema = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": 0,
            "itemsPerPage": 50,
            "startIndex": 1,
            "Resources": [],
        }
        result = self.client_get(
            f'/scim/v2/Groups?filter=displayName eq "{test_group.name}"',
            {},
            **self.scim_headers(),
        )
        self.assertEqual(result.status_code, 200)

        output_data = orjson.loads(result.content)
        self.assertEqual(output_data, expected_response_schema)

    def test_get_all_with_pagination(self) -> None:
        realm = get_realm("zulip")

        result_all = self.client_get("/scim/v2/Groups", {}, **self.scim_headers())
        self.assertEqual(result_all.status_code, 200)
        output_data_all = orjson.loads(result_all.content)

        expected_response_schema = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": NamedUserGroup.objects.filter(realm_for_sharding=realm).count(),
            "itemsPerPage": 50,
            "startIndex": 1,
            "Resources": [
                self.generate_group_schema(group)
                for group in NamedUserGroup.objects.filter(realm_for_sharding=realm).order_by("id")
            ],
        }

        self.assertEqual(output_data_all, expected_response_schema)

        # Next we test pagination, just like in TestSCIMUser.test_get_all_with_pagination.
        result_offset_limited = self.client_get(
            "/scim/v2/Groups?startIndex=4&count=3", {}, **self.scim_headers()
        )
        self.assertEqual(result_offset_limited.status_code, 200)
        output_data_offset_limited = orjson.loads(result_offset_limited.content)
        self.assertEqual(output_data_offset_limited["itemsPerPage"], 3)
        self.assertEqual(output_data_offset_limited["startIndex"], 4)
        self.assertEqual(
            output_data_offset_limited["totalResults"], output_data_all["totalResults"]
        )
        self.assert_length(output_data_offset_limited["Resources"], 3)

        self.assertEqual(output_data_offset_limited["Resources"], output_data_all["Resources"][3:6])

    def test_post(self) -> None:
        payload: dict[str, Any] = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "displayName": "New group without members",
            "members": [],
        }
        original_group_count = NamedUserGroup.objects.count()
        result = self.client_post(
            "/scim/v2/Groups", payload, content_type="application/json", **self.scim_headers()
        )
        self.assertEqual(result.status_code, 201)
        output_data = orjson.loads(result.content)

        self.assertEqual(NamedUserGroup.objects.count(), original_group_count + 1)

        new_group = NamedUserGroup.objects.latest("id")
        self.assertEqual(new_group.name, "New group without members")
        self.assertEqual(set(get_user_group_direct_member_ids(new_group)), set())

        expected_response_schema = self.generate_group_schema(new_group)
        self.assertEqual(expected_response_schema, output_data)

        hamlet = self.example_user("hamlet")
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "displayName": "New group with members",
            "members": [{"value": str(hamlet.id)}],
        }
        result = self.client_post(
            "/scim/v2/Groups", payload, content_type="application/json", **self.scim_headers()
        )
        self.assertEqual(result.status_code, 201)
        output_data = orjson.loads(result.content)

        self.assertEqual(NamedUserGroup.objects.count(), original_group_count + 2)

        new_group = NamedUserGroup.objects.latest("id")
        self.assertEqual(new_group.name, "New group with members")
        self.assertEqual(set(get_user_group_direct_member_ids(new_group)), {hamlet.id})

        expected_response_schema = self.generate_group_schema(new_group)
        self.assertEqual(expected_response_schema, output_data)

        # Can't create a group with a name that already matches another group.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "displayName": new_group.name,
            "members": [{"value": str(hamlet.id)}],
        }
        result = self.client_post(
            "/scim/v2/Groups", payload, content_type="application/json", **self.scim_headers()
        )
        self.assertEqual(
            orjson.loads(result.content),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": f"Group name already in use: {new_group.name}",
                "status": 409,
                "scimType": "uniqueness",
            },
        )

    def test_put_change_name_and_members(self) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        desdemona = self.example_user("desdemona")
        othello = self.example_user("othello")

        test_group = check_add_user_group(
            realm, "Test group", [hamlet, desdemona], acting_user=desdemona
        )

        # PUT replaces all specified attributes of the group. Thus,
        # this payload will replace both the name and set of members of
        # the group.
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "id": test_group.id,
            "displayName": "New test group name",
            "members": [{"value": str(hamlet.id)}, {"value": str(othello.id)}],
        }
        result = self.json_put(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        test_group.refresh_from_db()
        self.assertEqual(test_group.name, "New test group name")
        new_member_ids = get_user_group_direct_member_ids(test_group)
        self.assertEqual(set(new_member_ids), {hamlet.id, othello.id})

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_group_schema(test_group)
        self.assertEqual(output_data, expected_response_schema)

        conflicting_group = check_add_user_group(
            realm, "Conflicting group", [hamlet, desdemona], acting_user=desdemona
        )
        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "id": test_group.id,
            "displayName": conflicting_group.name,
            "members": [{"value": str(hamlet.id)}, {"value": str(othello.id)}],
        }
        result = self.json_put(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(
            orjson.loads(result.content),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": f"Group name already in use: {conflicting_group.name}",
                "status": 409,
                "scimType": "uniqueness",
            },
        )

        # Deactivated groups are invisible to SCIM.
        do_deactivate_user_group(test_group, acting_user=None)

        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "id": test_group.id,
            "displayName": "some new name - but group should not get updated",
            "members": [{"value": str(hamlet.id)}, {"value": str(othello.id)}],
        }
        result = self.json_put(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(
            orjson.loads(result.content),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": f"Resource {test_group.id} not found",
                "status": 404,
            },
        )
        test_group.refresh_from_db()
        self.assertEqual(test_group.name, "New test group name")

    def test_patch_add_remove_operations(self) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        desdemona = self.example_user("desdemona")
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")

        test_group = check_add_user_group(
            realm, "Test group", [hamlet, desdemona], acting_user=desdemona
        )

        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "add",
                    "path": "members",
                    "value": [
                        {"value": str(othello.id)},
                        {"value": str(cordelia.id)},
                        # Include a user who's already in the group in this list, to verify that trying to add
                        # a user who's already in the group is gracefully ignored.
                        {"value": str(desdemona.id)},
                    ],
                }
            ],
        }

        result = self.json_patch(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        self.assertEqual(
            set(get_user_group_direct_member_ids(test_group)),
            {hamlet.id, desdemona.id, othello.id, cordelia.id},
        )

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_group_schema(test_group)
        self.assertEqual(output_data, expected_response_schema)

        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "remove",
                    "path": "members",
                    # Similarly to the user addition case, here, for user removal,
                    # we include a user who's not in the group. Trying to remove a user
                    # who's not in the group should gracefully be ignored.
                    "value": [
                        {"value": str(othello.id)},
                        {"value": str(cordelia.id)},
                        {"value": str(iago.id)},
                    ],
                }
            ],
        }

        result = self.json_patch(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        self.assertEqual(
            set(get_user_group_direct_member_ids(test_group)), {hamlet.id, desdemona.id}
        )

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_group_schema(test_group)
        self.assertEqual(output_data, expected_response_schema)

        # Now try a sequence of operations and verify the final result
        # is as expected.
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "add",
                    "path": "members",
                    "value": [{"value": str(othello.id)}, {"value": str(cordelia.id)}],
                },
                {
                    "op": "remove",
                    "path": "members",
                    "value": [{"value": str(desdemona.id)}, {"value": str(hamlet.id)}],
                },
                {
                    "op": "add",
                    "path": "members",
                    "value": [{"value": str(hamlet.id)}],
                },
            ],
        }

        result = self.json_patch(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        self.assertEqual(
            set(get_user_group_direct_member_ids(test_group)), {hamlet.id, othello.id, cordelia.id}
        )

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_group_schema(test_group)
        self.assertEqual(output_data, expected_response_schema)

    def test_patch_remove_operation_with_complex_path(self) -> None:
        # We generally don't support PATCH requests with complex paths.
        # but have to make an exception for "remove a user from a group"
        # requests from Okta, which for some reason are sent with
        # complex paths.
        #
        # See ZulipSCIMGroup.handle_remove for details.
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        desdemona = self.example_user("desdemona")

        test_group = check_add_user_group(
            realm, "Test group", [hamlet, desdemona], acting_user=desdemona
        )
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "remove",
                    "path": f'members[value eq "{hamlet.id!s}"]',
                }
            ],
        }

        result = self.json_patch(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        self.assertEqual(set(get_user_group_direct_member_ids(test_group)), {desdemona.id})

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_group_schema(test_group)
        self.assertEqual(output_data, expected_response_schema)

    def test_patch_replace_operation(self) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        desdemona = self.example_user("desdemona")
        othello = self.example_user("othello")

        test_group = check_add_user_group(
            realm, "Test group", [hamlet, desdemona], acting_user=desdemona
        )

        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {"op": "replace", "path": "displayName", "value": "New test group name"}
            ],
        }

        result = self.json_patch(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        test_group.refresh_from_db()
        self.assertEqual(test_group.name, "New test group name")

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_group_schema(test_group)
        self.assertEqual(output_data, expected_response_schema)

        # Next try editing members.
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "replace",
                    "path": "members",
                    "value": [
                        {"value": str(hamlet.id)},
                        {"value": str(othello.id)},
                    ],
                }
            ],
        }
        result = self.json_patch(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        self.assertEqual(set(get_user_group_direct_member_ids(test_group)), {hamlet.id, othello.id})

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_group_schema(test_group)
        self.assertEqual(output_data, expected_response_schema)

        # The operation might also specify the attributes to replace by passing a dict
        # in the "value" key, instead of providing a "path".
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "replace",
                    "value": {"id": str(test_group.id), "displayName": "New test group name 2"},
                }
            ],
        }

        result = self.json_patch(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        test_group.refresh_from_db()
        self.assertEqual(test_group.name, "New test group name 2")

        output_data = orjson.loads(result.content)
        expected_response_schema = self.generate_group_schema(test_group)
        self.assertEqual(output_data, expected_response_schema)

        # Finally, update both SCIM attributes (displayName and members) in a single operation.
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "replace",
                    "value": {
                        "id": str(test_group.id),
                        "displayName": "New test group name 3",
                        "members": [
                            {"value": str(hamlet.id)},
                            {"value": str(othello.id)},
                            {"value": str(desdemona.id)},
                        ],
                    },
                }
            ],
        }
        result = self.json_patch(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(result.status_code, 200)

        test_group.refresh_from_db()
        self.assertEqual(test_group.name, "New test group name 3")
        self.assertEqual(
            set(get_user_group_direct_member_ids(test_group)), {hamlet.id, othello.id, desdemona.id}
        )

    def test_patch_add_user_wrong_realm(self) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        mit_user = self.mit_user("sipbtest")
        desdemona = self.example_user("desdemona")
        othello = self.example_user("othello")

        test_group = check_add_user_group(
            realm, "Test group", [hamlet, desdemona], acting_user=desdemona
        )

        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "add",
                    "path": "members",
                    "value": [
                        {"value": str(othello.id)},
                        # Also include an id of a user from a different realm.
                        {"value": str(mit_user.id)},
                    ],
                }
            ],
        }

        result = self.json_patch(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(
            orjson.loads(result.content),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": "Users outside of the realm can't be removed or added to the group",
                "status": 400,
            },
        )

        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "add",
                    "path": "members",
                    "value": [
                        # Try a request with just the id of a user from a different realm.
                        {"value": str(mit_user.id)},
                    ],
                }
            ],
        }

        result = self.json_patch(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(
            orjson.loads(result.content),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": "Users outside of the realm can't be removed or added to the group",
                "status": 400,
            },
        )

        # The requests failed, so there's no change in memberships.
        self.assertEqual(
            set(get_user_group_direct_member_ids(test_group)),
            {hamlet.id, desdemona.id},
        )

    def test_patch_add_invalid_user_id(self) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        desdemona = self.example_user("desdemona")
        othello = self.example_user("othello")

        test_group = check_add_user_group(
            realm, "Test group", [hamlet, desdemona], acting_user=desdemona
        )

        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "add",
                    "path": "members",
                    "value": [
                        {"value": str(othello.id)},
                        # Also include an id that doesn't match any user.
                        {"value": "987654321"},
                    ],
                }
            ],
        }

        result = self.json_patch(f"/scim/v2/Groups/{test_group.id}", payload, **self.scim_headers())
        self.assertEqual(
            orjson.loads(result.content),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": "Invalid user ids found in the request: {987654321}",
                "status": 400,
            },
        )

        # The request failed, so there's no change in memberships.
        self.assertEqual(
            set(get_user_group_direct_member_ids(test_group)),
            {hamlet.id, desdemona.id},
        )

    def test_cant_edit_system_groups(self) -> None:
        """
        Verifies that system groups are not allowed to be managed by SCIM requests.
        """
        realm = get_realm("zulip")
        system_group = NamedUserGroup.objects.get(realm_for_sharding=realm, name="role:owners")

        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {"op": "replace", "path": "displayName", "value": "New test group name"}
            ],
        }

        result = self.json_patch(
            f"/scim/v2/Groups/{system_group.id}", payload, **self.scim_headers()
        )
        self.assertEqual(
            orjson.loads(result.content),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": "Group role:owners can't be managed by SCIM.",
                "status": 400,
            },
        )
        system_group.refresh_from_db()
        self.assertEqual(system_group.name, "role:owners")

        result = self.client_delete(f"/scim/v2/Groups/{system_group.id}", **self.scim_headers())
        self.assertEqual(
            orjson.loads(result.content),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": "Group role:owners can't be managed by SCIM.",
                "status": 400,
            },
        )
        self.assertTrue(
            NamedUserGroup.objects.filter(realm_for_sharding=realm, name="role:owners").exists()
        )

        payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "displayName": "role:doesntexistyet",
            "members": [],
        }
        original_group_count = NamedUserGroup.objects.count()
        result = self.client_post(
            "/scim/v2/Groups", payload, content_type="application/json", **self.scim_headers()
        )
        self.assertEqual(
            orjson.loads(result.content),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": "User group name cannot start with 'role:'.",
                "status": 400,
            },
        )
        self.assertEqual(original_group_count, NamedUserGroup.objects.count())

    def test_endpoints_disabled(self) -> None:
        with self.assertLogs("django.request", "ERROR") as m:
            result = self.client_post(
                "/scim/v2/Groups/.search",
                {},
                content_type="application/json",
                **self.scim_headers(),
            )
            self.assertEqual(result.status_code, 501)
            self.assertEqual(
                m.output, ["ERROR:django.request:Not Implemented: /scim/v2/Groups/.search"]
            )

    def test_delete(self) -> None:
        # The DELETE endpoint is currently disabled.

        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        desdemona = self.example_user("desdemona")

        test_group = check_add_user_group(
            realm, "Test group", [hamlet, desdemona], acting_user=desdemona
        )

        with self.assertLogs("django.request", "ERROR") as m:
            result = self.client_delete(f"/scim/v2/Groups/{test_group.id}", **self.scim_headers())
            self.assertEqual(result.status_code, 501)
            self.assertEqual(
                m.output, [f"ERROR:django.request:Not Implemented: /scim/v2/Groups/{test_group.id}"]
            )


class TestRemainingUnsupportedSCIMFeatures(SCIMTestCase):
    def test_endpoints_disabled(self) -> None:
        for url in [
            "/scim/v2/",
            "/scim/v2/.search",
            "/scim/v2/Bulk",
            "/scim/v2/Me",
            "/scim/v2/ResourceTypes",
            "/scim/v2/Schemas",
            "/scim/v2/ServiceProviderConfig",
        ]:
            with self.assertLogs("django.request", "ERROR") as m:
                result = self.client_get(url, {}, **self.scim_headers())
            self.assertEqual(result.status_code, 501)
            self.assertEqual(m.output, [f"ERROR:django.request:Not Implemented: {url}"])
