from typing import Any, TypeAlias

import orjson
from typing_extensions import override

from zerver.lib.narrow import BadNarrowOperatorError, InvalidOperatorCombinationError
from zerver.lib.narrow_helpers import NarrowTerm
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_decoding import Filter, is_same_server_message_link, parse_narrow_url
from zerver.lib.url_encoding import hash_util_encode
from zerver.models.realms import get_realm

NarrowTermFixtureT: TypeAlias = dict[str, dict[str, list[dict[str, Any]]]]


class URLDecodeTest(ZulipTestCase):
    def test_is_same_server_message_link(self) -> None:
        tests = orjson.loads(self.fixture_data("message_link_test_cases.json"))
        for test in tests:
            self.assertEqual(
                is_same_server_message_link(test["message_link"]), test["expected_output"]
            )


class NarrowURLDecodeTest(ZulipTestCase):
    def test_decode_narrow_url(self) -> None:
        tests = orjson.loads(self.fixture_data("narrow_url_to_narrow_terms.json"))

        for test_case in tests:
            with self.subTest(name=test_case["name"]):
                parsed_terms = parse_narrow_url(test_case["near_link"])
                expected_output = test_case.get("expected_output")

                if expected_output is None:
                    self.assertEqual(parsed_terms, expected_output)
                else:
                    assert parsed_terms is not None
                    expected_narrow_terms: list[NarrowTerm] = [
                        NarrowTerm(**term) for term in expected_output
                    ]
                    self.assertListEqual(parsed_terms, expected_narrow_terms)


class NarrowTermFilterTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        self.realm = get_realm("zulip")
        return super().setUp()

    def test_initialize_narrow_terms(self) -> None:
        tests: NarrowTermFixtureT = orjson.loads(self.fixture_data("narrow_term_fixture.json"))
        for test_name, test_case in tests.items():
            narrow_terms_input = [NarrowTerm(**term) for term in test_case["valid_terms"]]
            filter_instance = Filter(narrow_terms_input, self.realm)
            actual_output = filter_instance.terms()

            with self.subTest(name=test_name):
                expected_output: list[NarrowTerm] = [
                    NarrowTerm(**term) for term in test_case["expected_output"]
                ]
                self.assertListEqual(actual_output, expected_output)

                for invalid_term in test_case["invalid_terms"]:
                    with self.assertRaises(BadNarrowOperatorError):
                        Filter([NarrowTerm(**invalid_term)], self.realm)

    def test_get_operands(self) -> None:
        fixture_terms = [
            NarrowTerm(negated=False, operator="channel", operand="13"),
            NarrowTerm(negated=False, operator="channel", operand="2"),
            NarrowTerm(negated=True, operator="channel", operand="88"),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
            NarrowTerm(negated=False, operator="topic", operand="testing2"),
            NarrowTerm(negated=False, operator="near", operand="1"),
            NarrowTerm(negated=False, operator="near", operand="2"),
        ]
        filter = Filter(fixture_terms, self.realm)

        self.assertEqual(filter.operands("channel"), [13, 2])
        self.assertEqual(filter.operands("topic"), ["testing", "testing2"])
        self.assertEqual(filter.operands("near"), [1, 2])
        self.assertEqual(filter.operands("stream"), [])

    def test_get_terms(self) -> None:
        fixture_terms = [
            NarrowTerm(negated=False, operator="channel", operand="13"),
            NarrowTerm(negated=False, operator="channel", operand="2"),
            NarrowTerm(negated=True, operator="channel", operand="88"),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
            NarrowTerm(negated=False, operator="topic", operand="testing2"),
            NarrowTerm(negated=False, operator="near", operand="1"),
            NarrowTerm(negated=False, operator="near", operand="2"),
        ]
        filter = Filter(fixture_terms, self.realm)

        self.assertEqual(
            filter.get_terms("channel"),
            [
                NarrowTerm(negated=False, operator="channel", operand=13),
                NarrowTerm(negated=False, operator="channel", operand=2),
                NarrowTerm(negated=True, operator="channel", operand=88),
            ],
        )
        self.assertEqual(
            filter.get_terms("topic"),
            [
                NarrowTerm(negated=False, operator="topic", operand="testing"),
                NarrowTerm(negated=False, operator="topic", operand="testing2"),
            ],
        )
        self.assertEqual(filter.get_terms("stream"), [])

    def test_build_sorted_narrow_term(self) -> None:
        expected_order = ["channel", "topic", "near"]

        inverted_order = [
            NarrowTerm(negated=False, operator="near", operand=1),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
            NarrowTerm(negated=False, operator="channel", operand=13),
        ]
        filter = Filter(inverted_order, self.realm)
        filter._build_sorted_term_types()
        self.assertEqual(filter._sorted_term_types, expected_order)

        correct_order = [
            NarrowTerm(negated=False, operator="channel", operand=13),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
            NarrowTerm(negated=False, operator="near", operand=1),
        ]
        filter = Filter(correct_order, self.realm)
        filter._build_sorted_term_types()
        self.assertEqual(filter._sorted_term_types, expected_order)

        term_types = Filter.sorted_term_types(
            ["channel", "unknown_term1", "unknown_term2", "topic"]
        )
        self.assertEqual(term_types, ["channel", "topic", "unknown_term1", "unknown_term2"])

    def test_update_term(self) -> None:
        base_terms = [
            NarrowTerm(negated=False, operator="near", operand=1),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
        ]

        old_term = NarrowTerm(negated=False, operator="channel", operand=13)
        old_terms = [*base_terms, old_term]
        filter = Filter(old_terms, self.realm)

        new_term = NarrowTerm(negated=False, operator="channel", operand=12)
        new_terms = [*base_terms, new_term]
        filter.update_term(old_term, new_term)

        self.assertEqual(filter.terms(), new_terms)

        filter = Filter(base_terms, self.realm)
        with self.assertRaisesRegex(AssertionError, "Invalid term to update"):
            filter.update_term(old_term, new_term)

    def test_check_either_channel_or_dm_narrow(self) -> None:
        channel_terms = [
            NarrowTerm(negated=False, operator="channel", operand=13),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
            NarrowTerm(negated=False, operator="near", operand=1),
        ]
        filter = Filter(channel_terms, self.realm)
        self.assertTrue(filter._check_either_channel_or_dm_narrow())

        dm_terms = [
            NarrowTerm(negated=False, operator="dm", operand=[13, 2]),
            NarrowTerm(negated=False, operator="near", operand=1),
        ]
        filter = Filter(dm_terms, self.realm)
        self.assertFalse(filter._check_either_channel_or_dm_narrow())

        invalid_terms = [
            NarrowTerm(negated=False, operator="channel", operand="13"),
            NarrowTerm(negated=False, operator="dm", operand="13"),
        ]
        with self.assertRaisesRegex(
            InvalidOperatorCombinationError,
            "No message can be both a channel message and direct message",
        ):
            Filter(invalid_terms, self.realm)._check_either_channel_or_dm_narrow()

        invalid_terms = [
            NarrowTerm(negated=False, operator="has", operand="images"),
        ]
        with self.assertRaisesRegex(
            InvalidOperatorCombinationError,
            "Not a channel message nor a direct message",
        ):
            Filter(invalid_terms, self.realm)._check_either_channel_or_dm_narrow()

    def test_generate_channel_url(self) -> None:
        channel_terms = [
            NarrowTerm(negated=False, operator="channel", operand=13),
        ]
        filter = Filter(channel_terms, self.realm)
        channel_url = filter.generate_channel_url()
        self.assertEqual(channel_url, "#narrow/channel/13-Venice")

        channel_terms = [
            NarrowTerm(negated=False, operator="channel", operand="Venice"),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
            NarrowTerm(negated=False, operator="near", operand=1),
        ]
        filter = Filter(channel_terms, self.realm)
        channel_url = filter.generate_channel_url()
        self.assertEqual(channel_url, "#narrow/channel/13-Venice")

        # Unknown channel
        channel_terms = [
            NarrowTerm(negated=False, operator="channel", operand="Venus"),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
            NarrowTerm(negated=False, operator="near", operand=1),
        ]
        filter = Filter(channel_terms, self.realm)
        with self.assertRaisesRegex(BadNarrowOperatorError, "unknown channel Venus"):
            filter.generate_channel_url()

        # No channel operand
        dm_terms = [
            NarrowTerm(negated=False, operator="dm", operand=13),
        ]
        filter = Filter(dm_terms, self.realm)
        with self.assertRaisesRegex(
            InvalidOperatorCombinationError, "Requires exactly one 'channel' operand"
        ):
            channel_url = filter.generate_channel_url()

    def test_generate_topic_url(self) -> None:
        channel_terms = [
            NarrowTerm(negated=False, operator="channel", operand=13),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
        ]
        terms = Filter(channel_terms, self.realm)
        channel_url = terms.generate_topic_url()
        self.assertEqual(channel_url, "#narrow/channel/13-Venice/topic/testing")

        channel_terms = [
            NarrowTerm(negated=False, operator="channel", operand=13),
            NarrowTerm(
                negated=False,
                operator="topic",
                operand="Broken Inline giphy preview / Messed up with camo :)",
            ),
            NarrowTerm(negated=False, operator="near", operand=1),
        ]
        terms = Filter(channel_terms, self.realm)
        channel_url = terms.generate_topic_url()
        self.assertEqual(
            channel_url,
            "#narrow/channel/13-Venice/topic/Broken.20Inline.20giphy.20preview.20.2F.20Messed.20up.20with.20camo.20.3A.29",
        )

        # No topic operand
        dm_terms = [
            NarrowTerm(negated=False, operator="channel", operand=13),
        ]
        terms = Filter(dm_terms, self.realm)
        with self.assertRaisesRegex(
            InvalidOperatorCombinationError, "Requires exactly one 'topic' operand"
        ):
            channel_url = terms.generate_topic_url()

    def test_generate_dm_with_url(self) -> None:
        hamlet = self.example_user("hamlet")
        dm_terms = [
            NarrowTerm(negated=False, operator="dm", operand=[hamlet.id]),
        ]
        terms = Filter(dm_terms, self.realm)
        channel_url = terms.generate_dm_with_url()
        self.assertEqual(
            channel_url, f"#narrow/dm/{hamlet.id}-{hash_util_encode(hamlet.full_name)}"
        )

        iago = self.example_user("iago")
        user_ids = [hamlet.id, iago.id]
        dm_terms = [
            NarrowTerm(negated=False, operator="dm", operand=user_ids),
        ]
        terms = Filter(dm_terms, self.realm)
        channel_url = terms.generate_dm_with_url()
        self.assertEqual(channel_url, "#narrow/dm/10,11-group")

        emails_string = f"{hamlet.email},{iago.email}"
        dm_terms = [
            NarrowTerm(negated=False, operator="dm", operand=emails_string),
        ]
        terms = Filter(dm_terms, self.realm)
        channel_url = terms.generate_dm_with_url()
        self.assertEqual(channel_url, "#narrow/dm/10,11-group")

        dm_terms = [
            NarrowTerm(negated=False, operator="dm", operand=emails_string + ",no-face@zulip.com"),
        ]
        terms = Filter(dm_terms, self.realm)
        with self.assertRaisesRegex(
            BadNarrowOperatorError,
            "unknown user in user10@zulip.testserver,user11@zulip.testserver,no-face@zulip.com",
        ):
            terms.generate_dm_with_url()

        channel_terms = [
            NarrowTerm(negated=False, operator="channel", operand=13),
        ]
        terms = Filter(channel_terms, self.realm)
        with self.assertRaisesRegex(
            InvalidOperatorCombinationError,
            "Requires exactly one 'dm' operand",
        ):
            terms.generate_dm_with_url()
