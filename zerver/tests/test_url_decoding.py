import orjson

from zerver.lib.narrow_helpers import NarrowTerm
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_decoding import Filter, is_same_server_message_link, parse_narrow_url


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
    def test_canonicalize_and_validate_terms(self) -> None:
        tests = orjson.loads(self.fixture_data("narrow_term_fixture.json"))
        for test_name, test_cases in tests.items():
            for test_case in test_cases:
                term = NarrowTerm(**test_case["term"])
                with self.subTest(name=test_name, term=term):
                    # Terms that canonicalizing doesn't change omit `canonical_term`.
                    expected_canonical_term = NarrowTerm(
                        **test_case.get("canonical_term", test_case["term"])
                    )
                    canonical_term = Filter.canonicalize_term(term)
                    self.assertEqual(canonical_term, expected_canonical_term)
                    self.assertEqual(
                        Filter.is_valid_canonical_term(canonical_term), test_case["is_valid"]
                    )

    def test_overlong_digit_operands(self) -> None:
        overlong_digits = "9" * 4301
        for operator in ["id", "near", "with"]:
            with self.subTest(operator=operator):
                term = NarrowTerm(operator, overlong_digits, False)
                self.assertFalse(Filter.is_valid_canonical_term(term))

    def test_fix_redundant_is_private(self) -> None:
        dm_term = NarrowTerm(negated=False, operator="dm", operand=[1])
        near_term = NarrowTerm(negated=False, operator="near", operand=2)
        negated_is_dm_term = NarrowTerm(negated=True, operator="is", operand="dm")
        narrow_filter = Filter(
            [
                NarrowTerm(negated=False, operator="is", operand="private"),
                dm_term,
                near_term,
                negated_is_dm_term,
            ]
        )
        self.assertEqual(narrow_filter.terms(), [dm_term, near_term, negated_is_dm_term])

        # A negated `dm` term doesn't make `is:dm` redundant.
        negated_dm_term = NarrowTerm(negated=True, operator="dm", operand=[1])
        is_dm_term = NarrowTerm(negated=False, operator="is", operand="dm")
        narrow_filter = Filter([negated_dm_term, is_dm_term])
        self.assertEqual(narrow_filter.terms(), [negated_dm_term, is_dm_term])

    def test_filter_from_parsed_narrow_url(self) -> None:
        terms = parse_narrow_url("https://example.com/#narrow/channel/13-Denmark/topic/x/near/5")
        assert terms is not None
        narrow_filter = Filter(terms)
        self.assertEqual(
            narrow_filter.terms(),
            [
                NarrowTerm(negated=False, operator="channel", operand=13),
                NarrowTerm(negated=False, operator="topic", operand="x"),
                NarrowTerm(negated=False, operator="near", operand=5),
            ],
        )
        for term in narrow_filter.terms():
            self.assertTrue(Filter.is_valid_canonical_term(term))

    def test_terms_with_operator(self) -> None:
        fixture_terms = [
            NarrowTerm(negated=False, operator="channel", operand=13),
            NarrowTerm(negated=False, operator="channel", operand=2),
            NarrowTerm(negated=True, operator="channel", operand=88),
            NarrowTerm(negated=False, operator="topic", operand="testing"),
            NarrowTerm(negated=False, operator="topic", operand="testing2"),
            NarrowTerm(negated=True, operator="dm", operand=[90]),
            NarrowTerm(negated=False, operator="near", operand=1),
            NarrowTerm(negated=False, operator="near", operand=2),
            NarrowTerm(negated=False, operator="with", operand="3"),
        ]
        narrow_filter = Filter(fixture_terms)

        self.assertEqual(
            narrow_filter.terms_with_operator("channel"),
            [
                NarrowTerm(negated=False, operator="channel", operand=13),
                NarrowTerm(negated=False, operator="channel", operand=2),
            ],
        )
        self.assertEqual(
            narrow_filter.terms_with_operator("topic"),
            [
                NarrowTerm(negated=False, operator="topic", operand="testing"),
                NarrowTerm(negated=False, operator="topic", operand="testing2"),
            ],
        )
        self.assertEqual(
            narrow_filter.terms_with_operator("near"),
            [
                NarrowTerm(negated=False, operator="near", operand=1),
                NarrowTerm(negated=False, operator="near", operand=2),
            ],
        )
        self.assertEqual(
            narrow_filter.terms_with_operator("with"),
            [
                NarrowTerm(negated=False, operator="with", operand="3"),
            ],
        )
        self.assertEqual(narrow_filter.terms_with_operator("dm"), [])
        self.assertEqual(narrow_filter.terms_with_operator("stream"), [])
