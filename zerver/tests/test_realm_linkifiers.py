import re

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import RealmFilter


class RealmFilterTest(ZulipTestCase):
    def test_list(self) -> None:
        self.login("iago")
        data = {
            "pattern": "#(?P<id>[123])",
            "url_format_string": "https://realm.com/my_realm_filter/%(id)s",
        }
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)

        data = {
            "pattern": "ticket-(?P<id>[0-9]+)",
            "url_format_string": "https://realm.com/ticket/%(id)s",
            "render_format_string": "Ticket-%(id)s",
        }
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)

        result = self.client_get("/json/realm/linkifiers")
        self.assert_json_success(result)
        linkifiers = result.json()["linkifiers"]
        self.assert_length(linkifiers, 2)
        self.assertEqual(linkifiers[0]["pattern"], "#(?P<id>[123])")
        self.assertEqual(linkifiers[0]["url_format"], "https://realm.com/my_realm_filter/%(id)s")

        self.assertEqual(linkifiers[1]["pattern"], "ticket-(?P<id>[0-9]+)")
        self.assertEqual(linkifiers[1]["url_format"], "https://realm.com/ticket/%(id)s")
        self.assertEqual(linkifiers[1]["render_format"], "Ticket-%(id)s")

    def test_create(self) -> None:
        self.login("iago")
        data = {"pattern": "", "url_format_string": "https://realm.com/my_realm_filter/%(id)s"}
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, "This field cannot be blank.")

        data["pattern"] = "$a"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(
            result, "Invalid linkifier pattern.  Valid characters are [ a-zA-Z_#=/:+!-]."
        )

        data["pattern"] = r"ZUL-(?P<id>\d++)"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(
            result, "Invalid linkifier pattern.  Valid characters are [ a-zA-Z_#=/:+!-]."
        )

        data["pattern"] = r"ZUL-(?P<id>\d+)"
        data["url_format_string"] = "$fgfg"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, "Enter a valid URL.")

        data["pattern"] = r"ZUL-(?P<id>\d+)"
        data["url_format_string"] = "https://realm.com/my_realm_filter/"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, "Invalid URL format string.")

        data["url_format_string"] = "https://realm.com/my_realm_filter/#hashtag/%(id)s"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "ZUL-15"))

        data["pattern"] = r"ZUL2-(?P<id>\d+)"
        data["url_format_string"] = "https://realm.com/my_realm_filter/?value=%(id)s"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "ZUL2-15"))

        data["pattern"] = r"_code=(?P<id>[0-9a-zA-Z]+)"
        data["url_format_string"] = "https://example.com/product/%(id)s/details"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "_code=123abcdZ"))

        data["pattern"] = r"PR (?P<id>[0-9]+)"
        data[
            "url_format_string"
        ] = "https://example.com/~user/web#view_type=type&model=model&action=12345&id=%(id)s"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "PR 123"))

        data["pattern"] = r"lp/(?P<id>[0-9]+)"
        data["url_format_string"] = "https://realm.com/my_realm_filter/?value=%(id)s&sort=reverse"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "lp/123"))

        data["pattern"] = r"lp:(?P<id>[0-9]+)"
        data["url_format_string"] = "https://realm.com/my_realm_filter/?sort=reverse&value=%(id)s"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "lp:123"))

        data["pattern"] = r"!(?P<id>[0-9]+)"
        data[
            "url_format_string"
        ] = "https://realm.com/index.pl?Action=AgentTicketZoom;TicketNumber=%(id)s"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "!123"))

        # This block of tests is for mismatches between field sets
        data["pattern"] = r"ZUL-(?P<id>\d+)"
        data["url_format_string"] = r"https://realm.com/my_realm_filter/%(hello)s"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(
            result, "Group 'hello' in URL format string is not present in linkifier pattern."
        )

        data["pattern"] = r"ZUL-(?P<id>\d+)-(?P<hello>\d+)"
        data["url_format_string"] = r"https://realm.com/my_realm_filter/%(hello)s"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(
            result, "Group 'id' in linkifier pattern is not present in URL format string."
        )

        data["pattern"] = r"ZULZ-(?P<hello>\d+)-(?P<world>\d+)"
        data["url_format_string"] = r"https://realm.com/my_realm_filter/%(hello)s/%(world)s"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)

        data["pattern"] = r"ZUL-(?P<id>\d+)-(?P<hello>\d+)-(?P<world>\d+)"
        data["url_format_string"] = r"https://realm.com/my_realm_filter/%(hello)s"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(
            result, "Group 'id' in linkifier pattern is not present in URL format string."
        )

        # BUG: In theory, this should be valid, since %% should be a
        # valid escaping method. It's unlikely someone actually wants
        # to do this, though.
        data["pattern"] = r"ZUL-(?P<id>\d+)"
        data["url_format_string"] = r"https://realm.com/my_realm_filter/%%(ignored)s/%(id)s"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, "Invalid URL format string.")

        data["pattern"] = r"(?P<org>[a-zA-Z0-9_-]+)/(?P<repo>[a-zA-Z0-9_-]+)#(?P<id>[0-9]+)"
        data["url_format_string"] = "https://github.com/%(org)s/%(repo)s/issue/%(id)s"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "zulip/zulip#123"))

        # Test with Render format string.
        data["pattern"] = r"#(?P<id>[0-9]{2,8})"
        data["url_format_string"] = r"https://trac.example.com/ticket/%(id)s"
        data["render_format_string"] = r"ticket-%(id)s"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "#1234"))

        data["render_format_string"] = "$foobar"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, "Invalid render format string.")

        data["render_format_string"] = r"ticket-%(num)s"
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(
            result, "Group 'num' in Render format string is not present in linkifier pattern."
        )

        # Render format string does not need to contain every parameter of the linkifier pattern.
        data["pattern"] = r"ZUL-#(?P<id>[0-9]+)"
        data["render_format_string"] = "ticket"
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
            "url_format_string": "https://realm.com/my_realm_filter/%(id)s",
        }
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)

        linkifier_id = result.json()["id"]
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
            "url_format_string": "https://realm.com/my_realm_filter/%(id)s",
        }
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)

        linkifier_id = result.json()["id"]
        data = {
            "pattern": "#(?P<id>[0-9]+)",
            "url_format_string": "https://realm.com/my_realm_filter/issues/%(id)s",
        }
        result = self.client_patch(f"/json/realm/filters/{linkifier_id}", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data["pattern"], "#1234"))

        # Verify that the linkifier is updated accordingly.
        result = self.client_get("/json/realm/linkifiers")
        self.assert_json_success(result)
        linkifier = result.json()["linkifiers"]
        self.assert_length(linkifier, 1)
        self.assertEqual(linkifier[0]["pattern"], "#(?P<id>[0-9]+)")
        self.assertEqual(
            linkifier[0]["url_format"], "https://realm.com/my_realm_filter/issues/%(id)s"
        )

        data = {
            "pattern": r"ZUL-(?P<id>\d++)",
            "url_format_string": "https://realm.com/my_realm_filter/%(id)s",
        }
        result = self.client_patch(f"/json/realm/filters/{linkifier_id}", info=data)
        self.assert_json_error(
            result, "Invalid linkifier pattern.  Valid characters are [ a-zA-Z_#=/:+!-]."
        )

        data["pattern"] = r"ZUL-(?P<id>\d+)"
        data["url_format_string"] = "$fgfg"
        result = self.client_patch(f"/json/realm/filters/{linkifier_id}", info=data)
        self.assert_json_error(result, "Enter a valid URL.")

        data["pattern"] = r"#(?P<id>[123])"
        data["url_format_string"] = "https://realm.com/my_realm_filter/%(id)s"
        result = self.client_patch(f"/json/realm/filters/{linkifier_id + 1}", info=data)
        self.assert_json_error(result, "Linkifier not found.")

        data["render_format_string"] = "ticket-%(id)s"
        result = self.client_patch(f"/json/realm/filters/{linkifier_id}", info=data)
        self.assert_json_success(result)

        data["render_format_string"] = "$foobar"
        result = self.client_patch(f"/json/realm/filters/{linkifier_id}", info=data)
        self.assert_json_error(result, "Invalid render format string.")
