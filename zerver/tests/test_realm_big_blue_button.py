from dataclasses import asdict
from typing import cast
from unittest.mock import MagicMock, patch

import zerver.models.realm_big_blue_button as bbb
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.realm_big_blue_button import (
    BigBlueButtonOption,
    BigBlueButtonOptionBool,
    BigBlueButtonOptionList,
    BigBlueButtonOptionStr,
    RealmBigBlueButton,
    create_model_from_option,
    flatten_params,
    get_all_big_blue_button_options_uncached,
    merge_big_blue_button_options_defaults,
    parse_boolean_option,
    update_big_blue_button_option,
)
from zerver.models.realms import get_realm


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
            BigBlueButtonOptionStr(option="a", data_type="str", real_option="", value="test"),
            BigBlueButtonOptionBool(option="b", data_type="bool", real_option="", value=False),
        ]

        result = flatten_params(options)

        self.assertEqual(result["a"], "test")
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

    def test_merge_returns_existing_db_object(self) -> None:
        realm = get_realm("zulip")

        know_option = BigBlueButtonOption(
            option="recording_enabled",
            default="False",
            translation="Record Meetings",
            parameter_type="create_param",
        )
        bbb.KnownBigBlueButtonOptions.append(know_option)

        RealmBigBlueButton.objects.create(
            realm=realm,
            option="recording_enabled",
            value="True",
            data_type="bool",
            parameter_type="create_param",
            real_option="",
        )

        results = merge_big_blue_button_options_defaults(realm.id)

        try:
            db_option = next(
                (
                    o
                    for o in results
                    if isinstance(o, RealmBigBlueButton) and o.option == "recording_enabled"
                ),
                None,
            )
            self.assertIsNotNone(db_option)
            assert db_option is not None
            self.assertEqual(db_option.value, "True")
            self.assertTrue(hasattr(db_option, "translation"))
        finally:
            bbb.KnownBigBlueButtonOptions.remove(know_option)

    def test_merge_returns_existing_db_object_list(self) -> None:
        realm = get_realm("zulip")

        know_option = BigBlueButtonOptionList(
            option="recording_enabled",
            default="False",
            translation="Record Meetings",
            parameter_type="create_param",
            list={"a": "A"},
        )
        bbb.KnownBigBlueButtonOptions.append(know_option)

        RealmBigBlueButton.objects.create(
            realm=realm,
            option="recording_enabled",
            value="True",
            data_type="bool",
            parameter_type="create_param",
            real_option="",
        )

        results = merge_big_blue_button_options_defaults(realm.id)

        try:
            db_option = next(
                (
                    o
                    for o in results
                    if isinstance(o, RealmBigBlueButton) and o.option == "recording_enabled"
                ),
                None,
            )
            self.assertIsNotNone(db_option)
            assert db_option is not None
            self.assertEqual(db_option.value, "True")
            self.assertTrue(hasattr(db_option, "translation"))
            self.assertEqual(db_option.list, {"a": "A"})
        finally:
            bbb.KnownBigBlueButtonOptions.remove(know_option)

    def test_merge_returns_default_if_not_in_db(self) -> None:
        realm = get_realm("zulip")

        results = merge_big_blue_button_options_defaults(realm.id)

        default_option = next(
            (
                o
                for o in results
                if isinstance(o, BigBlueButtonOption) and o.option == "mute_on_start"
            ),
            None,
        )
        self.assertIsNotNone(default_option)
        assert default_option is not None
        self.assertEqual(default_option.value, default_option.default)

    def test_parameter_type_filtering(self) -> None:
        realm = get_realm("zulip")

        RealmBigBlueButton.objects.create(
            realm=realm,
            option="recording_enabled",
            value="False",
            data_type="bool",
            parameter_type="join_param",
            real_option="",
        )

        RealmBigBlueButton.objects.create(
            realm=realm,
            option="recording_enabled",
            value="False",
            data_type="bool",
            parameter_type="create_param",
            real_option="",
        )

        results1 = merge_big_blue_button_options_defaults(realm.id, parameter_type="create_param")
        for o in results1:
            self.assertNotEqual(o.parameter_type, "join_param")
            self.assertEqual(o.parameter_type, "create_param")

        results2 = merge_big_blue_button_options_defaults(realm.id, parameter_type="join_param")
        for o in results2:
            self.assertNotEqual(o.parameter_type, "create_param")
            self.assertEqual(o.parameter_type, "join_param")

    def test_option_list_handling(self) -> None:
        realm = get_realm("zulip")

        list_option = BigBlueButtonOptionList(
            option="welcome_messages",
            default="en",
            list={"en": "Welcome", "de": "Willkommen"},
            translation="Welcome Messages",
            parameter_type="create_param",
        )

        bbb.KnownBigBlueButtonOptions.append(list_option)
        try:
            results = merge_big_blue_button_options_defaults(realm.id)
            found = next(
                (o for o in results if getattr(o, "option", None) == "welcome_messages"), None
            )
            self.assertIsNotNone(found)
            assert found is not None
            assert isinstance(found, BigBlueButtonOptionList)
            self.assertEqual(found.list, {"en": "Welcome", "de": "Willkommen"})
        finally:
            bbb.KnownBigBlueButtonOptions.remove(list_option)

    def test_get_all_options_uncached_list(self) -> None:
        fake = BigBlueButtonOptionList(
            id=1,
            option="c",
            value="",
            default="x",
            data_type="list",
            translation="C",
            list={"x": "X"},
            real_option="",
        )

        original_options = bbb.KnownBigBlueButtonOptions
        try:
            bbb.KnownBigBlueButtonOptions = [fake]

            result = get_all_big_blue_button_options_uncached(1)
            self.assertIn("c", result)

            option = result["c"]
            option = cast(BigBlueButtonOptionList, option)

            self.assertIsInstance(option, BigBlueButtonOptionList)
            self.assertEqual(option.list, {"x": "X"})
            self.assertEqual(option.value, "x")
        finally:
            bbb.KnownBigBlueButtonOptions = original_options

    def test_get_all_options_uncached_str(self) -> None:
        fake = BigBlueButtonOptionStr(
            id=1,
            option="d",
            value="",
            default="z",
            data_type="str",
            translation="D",
            real_option="",
        )

        original_options = bbb.KnownBigBlueButtonOptions
        try:
            bbb.KnownBigBlueButtonOptions = [fake]

            result = get_all_big_blue_button_options_uncached(1)
            self.assertIn("d", result)

            option = result["d"]
            option = cast(BigBlueButtonOptionStr, option)

            self.assertIsInstance(option, BigBlueButtonOptionStr)
            self.assertEqual(option.value, "z")
        finally:
            bbb.KnownBigBlueButtonOptions = original_options

    def test_create_model_from_option_found_and_not_found(self) -> None:
        fake_option = BigBlueButtonOptionStr(
            option="opt1",
            data_type="str",
            parameter_type="create_param",
            real_option="real_opt1",
        )

        original_options = bbb.KnownBigBlueButtonOptions
        try:
            bbb.KnownBigBlueButtonOptions = [fake_option]

            model = create_model_from_option(1, "opt1")
            self.assertIsNotNone(model)
            model = cast(RealmBigBlueButton, model)
            self.assertEqual(model.option, "opt1")
            self.assertEqual(model.real_option, "real_opt1")

            model_none = create_model_from_option(1, "unknown")
            self.assertIsNone(model_none)
        finally:
            bbb.KnownBigBlueButtonOptions = original_options

    def test_update_existing_option(self) -> None:
        realm = get_realm("zulip")

        bbb_option = RealmBigBlueButton.objects.create(
            realm=realm,
            option="example_option",
            value="old_value",
            data_type="str",
            parameter_type="create_param",
            real_option="",
        )

        update_big_blue_button_option(realm.id, "example_option", "new_value")

        bbb_option.refresh_from_db()
        self.assertEqual(bbb_option.value, "new_value")

    @patch("zerver.models.realm_big_blue_button.create_model_from_option")
    def test_create_new_option_if_not_exists(self, mock_create: MagicMock) -> None:
        realm = get_realm("zulip")

        mock_create.return_value = RealmBigBlueButton(
            realm=realm,
            option="new_option",
            value="",
            data_type="str",
            parameter_type="create_param",
            real_option="",
        )

        update_big_blue_button_option(realm.id, "new_option", True)

        mock_create.assert_called_once_with(realm_id=realm.id, option="new_option")
        obj = RealmBigBlueButton.objects.get(realm=realm, option="new_option")
        self.assertEqual(obj.value, "True")

    @patch("zerver.models.realm_big_blue_button.create_model_from_option")
    def test_raise_error_if_creation_fails(self, mock_create: MagicMock) -> None:
        realm = get_realm("zulip")
        mock_create.return_value = None

        with self.assertRaises(ValueError) as cm:
            update_big_blue_button_option(realm.id, "fail_option", "value")

        self.assertIn("could not created", str(cm.exception))
