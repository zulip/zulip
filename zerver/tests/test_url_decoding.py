from typing import Any, TypeAlias

import orjson

from zerver.lib.narrow import BadNarrowOperatorError
from zerver.lib.narrow_helpers import NarrowTerm
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_decoding import Filter, is_same_server_message_link, parse_narrow_url

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
    def test_initialize_narrow_terms(self) -> None:
        tests: NarrowTermFixtureT = orjson.loads(self.fixture_data("narrow_term_fixture.json"))
        for test_name, test_case in tests.items():
            narrow_terms_input = [NarrowTerm(**term) for term in test_case["valid_terms"]]
            filter_instance = Filter(narrow_terms_input)
            actual_output = filter_instance.terms()

            with self.subTest(name=test_name):
                expected_output: list[NarrowTerm] = [
                    NarrowTerm(**term) for term in test_case["expected_output"]
                ]
                self.assertListEqual(actual_output, expected_output)

                for invalid_term in test_case["invalid_terms"]:
                    with self.assertRaises(BadNarrowOperatorError):
                        Filter([NarrowTerm(**invalid_term)])

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
        filter = Filter(fixture_terms)

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
            NarrowTerm(negated=True, operator="dm", operand="90"),
            NarrowTerm(negated=False, operator="near", operand="1"),
            NarrowTerm(negated=False, operator="near", operand="2"),
            NarrowTerm(negated=False, operator="with", operand="3"),
        ]
        filter = Filter(fixture_terms)

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
        self.assertEqual(
            filter.get_terms("with"),
            [
                NarrowTerm(negated=False, operator="with", operand=3),
            ],
        )
        self.assertEqual(
            filter.get_terms("dm"),
            [
                NarrowTerm(negated=True, operator="dm", operand=[90]),
            ],
        )
        self.assertEqual(filter.get_terms("stream"), [])

    def test_sorted_terms(self) -> None:
        expected_order = [
            NarrowTerm(negated=False, operator="channel", operand=13),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
            NarrowTerm(negated=False, operator="near", operand=1),
        ]

        inverted_order = [
            NarrowTerm(negated=False, operator="near", operand=1),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
            NarrowTerm(negated=False, operator="channel", operand=13),
        ]
        sorted_terms = Filter.sorted_terms(inverted_order)
        self.assertEqual(sorted_terms, expected_order)

        correct_order = [
            NarrowTerm(negated=False, operator="channel", operand=13),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
            NarrowTerm(negated=False, operator="near", operand=1),
        ]
        sorted_terms = Filter.sorted_terms(correct_order)
        self.assertEqual(sorted_terms, expected_order)

        unknown_term = NarrowTerm(negated=False, operator="unknownterm", operand=13)
        terms = [
            unknown_term,
            NarrowTerm(negated=False, operator="topic", operand="testing"),
            NarrowTerm(negated=False, operator="near", operand=1),
        ]
        sorted_terms = Filter.sorted_terms(terms)
        self.assertEqual(sorted_terms[-1], unknown_term)

    def test_update_term(self) -> None:
        base_terms = [
            NarrowTerm(negated=False, operator="near", operand=1),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
        ]

        old_term = NarrowTerm(negated=False, operator="channel", operand=13)
        old_terms = [*base_terms, old_term]
        filter = Filter(old_terms)

        new_term = NarrowTerm(negated=False, operator="channel", operand=12)
        new_terms = [*base_terms, new_term]
        filter.update_term(old_term, new_term)

        self.assertEqual(filter.terms(), new_terms)

        filter = Filter(base_terms)
        with self.assertRaisesRegex(AssertionError, "Invalid term to update"):
            filter.update_term(old_term, new_term)
