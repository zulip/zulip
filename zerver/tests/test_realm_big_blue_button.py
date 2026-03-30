from dataclasses import asdict
from types import SimpleNamespace
from typing import Any, cast

from zerver.lib.test_classes import ZulipTestCase
from zerver.models.realm_big_blue_button import (
    BigBlueButtonOption,
    BigBlueButtonOptionBool,
    BigBlueButtonOptionList,
    BigBlueButtonOptionStr,
    KnownBigBlueButtonOptions,
    RealmBigBlueButton,
    create_model_from_option,
    flatten_params,
    get_all_big_blue_button_options_uncached,
    merge_big_blue_button_options_defaults,
    parse_boolean_option,
)


class TestRealmBigBlueButton(ZulipTestCase):
    def test_base_option_creation(self) -> None:
        opt = BigBlueButtonOption(
            option="record",
            translation="Aufzeichnung",
        )

        self.assertEqual(opt.id, -1)
        self.assertEqual(opt.option, "record")
        self.assertEqual(opt.translation, "Aufzeichnung")  # German
        self.assertEqual(opt.value, None)
        self.assertEqual(opt.default, None)
        self.assertEqual(opt.parameter_type, "str")
        self.assertEqual(opt.data_type, "create_param")
        self.assertEqual(opt.real_option, "")

    def test_base_option_custom_values(self) -> None:
        opt = BigBlueButtonOption(
            option="record",
            translation="Aufzeichnung",
            value="true",
            default="false",
            parameter_type="custom",
            data_type="update_param",
            real_option="recording",
        )

        self.assertEqual(opt.value, "true")
        self.assertEqual(opt.default, "false")
        self.assertEqual(opt.parameter_type, "custom")
        self.assertEqual(opt.data_type, "update_param")
        self.assertEqual(opt.real_option, "recording")

    def test_string_option_defaults(self) -> None:
        opt = BigBlueButtonOptionStr(
            option="welcome",
            translation="Begrüßung",
        )

        self.assertIsNone(opt.value)
        self.assertEqual(opt.default, "")

    def test_string_option_values(self) -> None:
        opt = BigBlueButtonOptionStr(
            option="welcome", translation="Begrüßung", value="Hallo", default="Hi"
        )

        self.assertEqual(opt.value, "Hallo")
        self.assertEqual(opt.default, "Hi")

    def test_bool_option_defaults(self) -> None:
        opt = BigBlueButtonOptionBool(
            option="record",
            translation="Aufzeichnung",
        )

        self.assertIsNone(opt.value)
        self.assertFalse(opt.default)

    def test_bool_option_values(self) -> None:
        opt = BigBlueButtonOptionBool(
            option="record", translation="Aufzeichnung", value=True, default=True
        )

        self.assertTrue(opt.value)
        self.assertTrue(opt.default)

    def test_list_option_defaults(self) -> None:
        opt = BigBlueButtonOptionList(
            option="lang",
            translation="Sprache",
        )

        self.assertIsNone(opt.value)
        self.assertEqual(opt.default, "")
        self.assertEqual(opt.list, {})

    def test_list_option_with_values(self) -> None:
        opt = BigBlueButtonOptionList(
            option="lang",
            translation="Sprache",
            value="de",
            default="en",
            list={"de": "Deutsch", "en": "English"},
        )

        self.assertEqual(opt.value, "de")
        self.assertEqual(opt.default, "en")
        self.assertEqual(opt.list["de"], "Deutsch")

    def test_asdict_conversion(self) -> None:
        opt = BigBlueButtonOptionStr(option="welcome", translation="Begrüßung", value="Hallo")

        data = asdict(opt)

        self.assertTrue(isinstance(data, dict))
        self.assertEqual(data["option"], "welcome")
        self.assertEqual(data["value"], "Hallo")

    def test_flatten_params_str_bool_list(self) -> None:
        options = [
            BigBlueButtonOption(option="a", value="hello", data_type="str", real_option=""),
            BigBlueButtonOption(option="b", value="true", data_type="bool", real_option=""),
            BigBlueButtonOption(option="c", value="x", data_type="list", real_option=""),
        ]

        result = flatten_params(options)

        self.assertEqual(result["a"], "hello")
        self.assertTrue(result["b"])
        self.assertEqual(result["c"], "x")

    def test_flatten_params_real_option_override(self) -> None:
        options = [
            BigBlueButtonOption(option="a", value="hello", data_type="str", real_option="real_a"),
        ]

        result = flatten_params(options)

        self.assertTrue("a" not in result)
        self.assertEqual(result["real_a"], "hello")

    def test_flatten_params_missing_value_defaults(self) -> None:
        options = [
            BigBlueButtonOption(option="a", data_type="str", real_option=""),
            BigBlueButtonOption(option="b", data_type="bool", real_option=""),
        ]

        result = flatten_params(options)

        self.assertEqual(result["a"], "")
        self.assertFalse(result["b"])

    def test_parse_boolean_option(self) -> None:
        self.assertTrue(parse_boolean_option("true"))
        self.assertTrue(parse_boolean_option("True"))
        self.assertTrue(parse_boolean_option("1"))
        self.assertFalse(parse_boolean_option("false"))
        self.assertFalse(parse_boolean_option("0"))
        self.assertFalse(parse_boolean_option(""))
        self.assertFalse(parse_boolean_option("random"))

    def test_flatten_params(self) -> None:
        options = [
            BigBlueButtonOptionStr(option="a", value="hello", data_type="str", real_option=""),
            BigBlueButtonOptionBool(option="b", value=True, data_type="bool", real_option=""),
            BigBlueButtonOptionList(option="c", value="x", data_type="list", real_option=""),
            BigBlueButtonOptionStr(option="d", value="x", data_type="str", real_option="real_d"),
        ]

        result = flatten_params(options)
        self.assertEqual(result["a"], "hello")
        self.assertTrue(result["b"])
        self.assertEqual(result["c"], "x")
        self.assertEqual(result["real_d"], "x")
        self.assertNotIn("d", result)

    def test_merge_defaults_adds_missing_and_merges_existing(self) -> None:
        fake_default = SimpleNamespace(
            option="opt1",
            translation="Option 1",
            data_type="str",
            parameter_type="create_param",
            real_option="",
        )

        original_merge = merge_big_blue_button_options_defaults

        try:
            globals()["merge_big_blue_button_options_defaults"] = (
                lambda realm_id, parameter_type=None: [fake_default]
            )

            options = merge_big_blue_button_options_defaults(realm_id=1)
            self.assertIn(fake_default, options)
        finally:
            globals()["merge_big_blue_button_options_defaults"] = original_merge

    def test_get_all_options_uncached_list(self) -> None:
        fake = BigBlueButtonOptionList(
            id=1,
            option="c",
            value="x",
            data_type="list",
            translation="C",
            list={"x": "X"},
            real_option="",
        )

        original_merge = merge_big_blue_button_options_defaults
        try:

            def fake_merge(realm_id: int, parameter_type: Any = None) -> list[Any]:
                return [fake]

            globals()["merge_big_blue_button_options_defaults"] = fake_merge

            result = get_all_big_blue_button_options_uncached(1)
            self.assertIn("c", result)

            option = result["c"]
            option = cast(BigBlueButtonOptionList, option)

            self.assertIsInstance(option, BigBlueButtonOptionList)
            self.assertEqual(option.list, {"x": "X"})
            self.assertEqual(option.value, "x")
        finally:
            globals()["merge_big_blue_button_options_defaults"] = original_merge

    def test_create_model_from_option_found_and_not_found(self) -> None:
        fake_option = SimpleNamespace(
            option="opt1",
            data_type="str",
            parameter_type="create_param",
            real_option="real_opt1",
        )

        original_options = list(KnownBigBlueButtonOptions)
        try:
            globals()["KnownBigBlueButtonOptions"] = [fake_option]

            model = create_model_from_option(1, "opt1")
            self.assertIsNotNone(model)
            model = cast(RealmBigBlueButton, model)
            self.assertEqual(model.option, "opt1")
            self.assertEqual(model.real_option, "real_opt1")

            model_none = create_model_from_option(1, "unknown")
            self.assertIsNone(model_none)
        finally:
            globals()["KnownBigBlueButtonOptions"] = original_options
