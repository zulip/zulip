import re
from typing import List

import orjson
from django.core.exceptions import ValidationError

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import RealmAuditLog, RealmFilter, url_template_validator


class RealmFilterTest(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        iago = self.example_user("iago")
        RealmFilter.objects.filter(realm=iago.realm).delete()

    def test_list(self) -> None:
        self.login("iago")
        data = {
            "pattern": "#(?P<id>[123])",
            "url_template": "https://realm.com/my_realm_filter/{id}",
        }
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)

        result = self.client_get("/json/realm/linkifiers")
        linkifiers = self.assert_json_success(result)["linkifiers"]
        self.assert_length(linkifiers, 1)
        self.assertEqual(linkifiers[0]["pattern"], "#(?P<id>[123])")
        self.assertEqual(linkifiers[0]["url_template"], "https://realm.com/my_realm_filter/{id}")

    def test_create(self) -> None:
        self.login("iago")
        data = {"pattern": "", "url_template": "https://realm.com/my_realm_filter/{id}"}
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, "This field cannot be blank.")

        data["pattern"] = "(foo"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, "Bad regular expression: missing ): (foo")

        data["pattern"] = r"ZUL-(?P<id>\d????)"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, "Bad regular expression: bad repetition operator: ????")

        data["pattern"] = r"ZUL-(?P<id>\d+)"
        data["url_template"] = "$fgfg"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(
            result, "Group 'id' in linkifier pattern is not present in URL template."
        )

        data["pattern"] = r"ZUL-(?P<id>\d+)"
        data["url_template"] = "https://realm.com/my_realm_filter/"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(
            result, "Group 'id' in linkifier pattern is not present in URL template."
        )

        data["url_template"] = "https://realm.com/my_realm_filter/#hashtag/{id}"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "ZUL-15"))

        data["pattern"] = r"ZUL2-(?P<id>\d+)"
        data["url_template"] = "https://realm.com/my_realm_filter/?value={id}"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "ZUL2-15"))

        data["pattern"] = r"_code=(?P<id>[0-9a-zA-Z]+)"
        data["url_template"] = "https://example.com/product/{id}/details"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "_code=123abcdZ"))

        data["pattern"] = r"PR (?P<id>[0-9]+)"
        data[
            "url_template"
        ] = "https://example.com/~user/web#view_type=type&model=model&action=12345&id={id}"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "PR 123"))

        data["pattern"] = r"lp/(?P<id>[0-9]+)"
        data["url_template"] = "https://realm.com/my_realm_filter/?value={id}&sort=reverse"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "lp/123"))

        data["pattern"] = r"lp:(?P<id>[0-9]+)"
        data["url_template"] = "https://realm.com/my_realm_filter/?sort=reverse&value={id}"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "lp:123"))

        data["pattern"] = r"!(?P<id>[0-9]+)"
        data["url_template"] = "https://realm.com/index.pl?Action=AgentTicketZoom;TicketNumber={id}"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "!123"))

        # This block of tests is for mismatches between field sets
        data["pattern"] = r"ZUL-(?P<id>\d+)"
        data["url_template"] = r"https://realm.com/my_realm_filter/{hello}"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(
            result, "Group 'hello' in URL template is not present in linkifier pattern."
        )

        data["pattern"] = r"ZUL-(?P<id>\d+)-(?P<hello>\d+)"
        data["url_template"] = r"https://realm.com/my_realm_filter/{hello}"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(
            result, "Group 'id' in linkifier pattern is not present in URL template."
        )

        data["pattern"] = r"ZULZ-(?P<hello>\d+)-(?P<world>\d+)"
        data["url_template"] = r"https://realm.com/my_realm_filter/{hello}/{world}"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)

        data["pattern"] = r"ZUL-(?P<id>\d+)-(?P<hello>\d+)-(?P<world>\d+)"
        data["url_template"] = r"https://realm.com/my_realm_filter/{hello}"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(
            result, "Group 'id' in linkifier pattern is not present in URL template."
        )

        data["pattern"] = r"ZUL-URL-(?P<id>\d+)"
        data["url_template"] = "https://example.com/%ba/{id}"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)

        data["pattern"] = r"(?P<org>[a-zA-Z0-9_-]+)/(?P<repo>[a-zA-Z0-9_-]+)#(?P<id>[0-9]+)"
        data["url_template"] = "https://github.com/{org}/{repo}/issue/{id}"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "zulip/zulip#123"))

        data[
            "pattern"
        ] = r"FOO_(?P<id>[a-f]{5});(?P<zone>[a-f]);(?P<domain>[a-z]+);(?P<location>[a-z]+);(?P<name>[a-z]{2,8});(?P<chapter>[0-9]{2,3});(?P<fragment>[a-z]{2,8})"
        data[
            "url_template"
        ] = "https://zone_{zone}{.domain}.net/ticket{/location}{/id}{?name,chapter}{#fragment:5}"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)

    def test_not_realm_admin(self) -> None:
        self.login("hamlet")
        result = self.client_post("/json/realm/filters")
        self.assert_json_error(result, "Must be an organization administrator")
        result = self.client_delete("/json/realm/filters/15")
        self.assert_json_error(result, "Must be an organization administrator")

    def test_delete(self) -> None:
        self.login("iago")
        data = {
            "pattern": "#(?P<id>[123])",
            "url_template": "https://realm.com/my_realm_filter/{id}",
        }
        result = self.client_post("/json/realm/filters", info=data)
        linkifier_id = self.assert_json_success(result)["id"]
        linkifiers_count = RealmFilter.objects.count()
        result = self.client_delete(f"/json/realm/filters/{linkifier_id + 1}")
        self.assert_json_error(result, "Linkifier not found.")

        result = self.client_delete(f"/json/realm/filters/{linkifier_id}")
        self.assert_json_success(result)
        self.assertEqual(RealmFilter.objects.count(), linkifiers_count - 1)

    def test_update(self) -> None:
        self.login("iago")
        data = {
            "pattern": "#(?P<id>[123])",
            "url_template": "https://realm.com/my_realm_filter/{id}",
        }
        result = self.client_post("/json/realm/filters", info=data)
        linkifier_id = self.assert_json_success(result)["id"]
        data = {
            "pattern": "#(?P<id>[0-9]+)",
            "url_template": "https://realm.com/my_realm_filter/issues/{id}",
        }
        result = self.client_patch(f"/json/realm/filters/{linkifier_id}", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "#1234"))

        # Verify that the linkifier is updated accordingly.
        result = self.client_get("/json/realm/linkifiers")
        linkifier = self.assert_json_success(result)["linkifiers"]
        self.assert_length(linkifier, 1)
        self.assertEqual(linkifier[0]["pattern"], "#(?P<id>[0-9]+)")
        self.assertEqual(
            linkifier[0]["url_template"], "https://realm.com/my_realm_filter/issues/{id}"
        )

        data = {
            "pattern": r"ZUL-(?P<id>\d????)",
            "url_template": "https://realm.com/my_realm_filter/{id}",
        }
        result = self.client_patch(f"/json/realm/filters/{linkifier_id}", info=data)
        self.assert_json_error(result, "Bad regular expression: bad repetition operator: ????")

        data["pattern"] = r"ZUL-(?P<id>\d+)"
        data["url_template"] = "$fgfg"
        result = self.client_patch(f"/json/realm/filters/{linkifier_id}", info=data)
        self.assert_json_error(
            result, "Group 'id' in linkifier pattern is not present in URL template."
        )

        data["pattern"] = r"#(?P<id>[123])"
        data["url_template"] = "https://realm.com/my_realm_filter/{id}"
        result = self.client_patch(f"/json/realm/filters/{linkifier_id + 1}", info=data)
        self.assert_json_error(result, "Linkifier not found.")

        data["pattern"] = r"#(?P<id>[123])"
        data["url_template"] = "{id"
        result = self.client_patch(f"/json/realm/filters/{linkifier_id}", info=data)
        self.assert_json_error(result, "Invalid URL template.")

    def test_valid_urls(self) -> None:
        valid_urls = [
            "http://example.com/",
            "https://example.com/",
            "https://user:password@example.com/",
            "https://example.com/@user/thing",
            "https://example.com/!path",
            "https://example.com/foo.bar",
            "https://example.com/foo[bar]",
            "https://example.com/{foo}",
            "https://example.com/{foo}{bars}",
            "https://example.com/{foo}/and/{bar}",
            "https://example.com/?foo={foo}",
            "https://example.com/%ab",
            "https://example.com/%ba",
            "https://example.com/%21",
            "https://example.com/words%20with%20spaces",
            "https://example.com/back%20to%20{back}",
            "https://example.com/encoded%2fwith%2fletters",
            "https://example.com/encoded%2Fwith%2Fupper%2Fcase%2Fletters",
            "https://example.com/%%",
            "https://example.com/%%(",
            "https://example.com/%%()",
            "https://example.com/%%(foo",
            "https://example.com/%%(foo)",
            "https://example.com/%%(foo)s",
            "https://example.com{/foo,bar,baz}",
            "https://example.com/{?foo*}",
            "https://example.com/{+foo,bar}",
            "https://chat{.domain}.com/{#foo}",
            "https://zone_{zone}{.domain}.net/ticket{/location}{/id}{?name,chapter}{#fragment:5}",
            "$not_a_url$",
        ]
        for url in valid_urls:
            url_template_validator(url)

        # No need to test this extensively, because most of the invalid
        # cases should be handled and tested in the uri_template library
        # we used for validation.
        invalid_urls = [
            "https://example.com/{foo",
            "https://example.com/{{}",
            "https://example.com/{//foo}",
            "https://example.com/{bar++}",
        ]
        for url in invalid_urls:
            with self.assertRaises(ValidationError):
                url_template_validator(url)

    def test_reorder_linkifiers(self) -> None:
        iago = self.example_user("iago")
        self.login("iago")

        def assert_linkifier_audit_logs(expected_id_order: List[int]) -> None:
            """Check if the audit log created orders the linkifiers correctly"""
            extra_data = (
                RealmAuditLog.objects.filter(
                    acting_user=iago, event_type=RealmAuditLog.REALM_LINKIFIERS_REORDERED
                )
                .latest("event_time")
                .extra_data
            )
            audit_logged_ids = [
                linkifier_dict["id"] for linkifier_dict in extra_data["realm_linkifiers"]
            ]
            self.assertListEqual(expected_id_order, audit_logged_ids)

        def assert_linkifier_order(expected_id_order: List[int]) -> None:
            """Verify that the realm audit log created matches the expected ordering"""
            result = self.client_get("/json/realm/linkifiers")
            actual_id_order = [
                linkifier["id"] for linkifier in self.assert_json_success(result)["linkifiers"]
            ]
            self.assertListEqual(expected_id_order, actual_id_order)

        def reorder_verify_succeed(expected_id_order: List[int]) -> None:
            """Send a reorder request and verify that it succeeds"""
            result = self.client_patch(
                "/json/realm/linkifiers",
                {"ordered_linkifier_ids": orjson.dumps(expected_id_order).decode()},
            )
            self.assert_json_success(result)

        reorder_verify_succeed([])
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=iago.realm, event_type=RealmAuditLog.REALM_LINKIFIERS_REORDERED
            ).count(),
            0,
        )

        linkifiers = [
            {
                "pattern": "1#(?P<id>[123])",
                "url_template": "https://filter.com/foo/{id}",
            },
            {
                "pattern": "2#(?P<id>[123])",
                "url_template": "https://filter.com/bar/{id}",
            },
            {
                "pattern": "3#(?P<id>[123])",
                "url_template": "https://filter.com/baz/{id}",
            },
        ]
        original_id_order = []
        for linkifier in linkifiers:
            result = self.client_post("/json/realm/filters", linkifier)
            original_id_order.append(self.assert_json_success(result)["id"])
        assert_linkifier_order(original_id_order)
        self.assertListEqual([0, 1, 2], list(RealmFilter.objects.values_list("order", flat=True)))

        # The creation order orders the linkifiers by default.
        # When the order values are the same, fallback to order by ID.
        RealmFilter.objects.all().update(order=0)
        assert_linkifier_order(original_id_order)

        # This should successfully reorder the linkifiers.
        new_order = [original_id_order[2], original_id_order[1], original_id_order[0]]
        reorder_verify_succeed(new_order)
        assert_linkifier_audit_logs(new_order)
        assert_linkifier_order(new_order)

        # After reordering, newly created linkifier is ordered at the last, and
        # the other linkifiers are unchanged.
        result = self.client_post(
            "/json/realm/filters", {"pattern": "3#123", "url_template": "https://example.com"}
        )
        new_linkifier_id = self.assert_json_success(result)["id"]
        new_order = [*new_order, new_linkifier_id]
        assert_linkifier_order(new_order)

        # Deleting a linkifier should preserve the order.
        deleted_linkifier_id = new_order[2]
        result = self.client_delete(f"/json/realm/filters/{deleted_linkifier_id}")
        self.assert_json_success(result)
        new_order = [*new_order[:2], new_linkifier_id]
        assert_linkifier_order(new_order)

        # Extra non-existent ids are ignored.
        new_order = [new_order[2], new_order[0], new_order[1]]
        result = self.client_patch(
            "/json/realm/linkifiers", {"ordered_linkifier_ids": [deleted_linkifier_id, *new_order]}
        )
        self.assert_json_error(
            result, "The ordered list must enumerate all existing linkifiers exactly once"
        )

        # Duplicated IDs are not allowed.
        new_order = [*new_order, new_order[0]]
        result = self.client_patch("/json/realm/linkifiers", {"ordered_linkifier_ids": new_order})
        self.assert_json_error(result, "The ordered list must not contain duplicated linkifiers")

        # Incomplete lists of linkifiers are not allowed.
        result = self.client_patch(
            "/json/realm/linkifiers", {"ordered_linkifier_ids": new_order[:2]}
        )
        self.assert_json_error(
            result, "The ordered list must enumerate all existing linkifiers exactly once"
        )
