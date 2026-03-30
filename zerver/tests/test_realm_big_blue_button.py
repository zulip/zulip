from dataclasses import asdict
from types import SimpleNamespace
from typing import Any

import pytest
from pytest import MonkeyPatch
from typing_extensions import Self

from zerver.models.realm_big_blue_button import (
    BigBlueButtonOption,
    BigBlueButtonOptionBool,
    BigBlueButtonOptionList,
    BigBlueButtonOptionStr,
    create_model_from_option,
    flatten_params,
    get_all_big_blue_button_options_uncached,
    merge_big_blue_button_options_defaults,
    parse_boolean_option,
    update_big_blue_button_option,
)


def test_base_option_creation() -> None:
    opt = BigBlueButtonOption(
        option="record",
        translation="Aufzeichnung",
    )

    assert opt.id == -1
    assert opt.option == "record"
    assert opt.translation == "Aufzeichnung"  # German
    assert opt.value is None
    assert opt.default is None
    assert opt.parameter_type == "str"
    assert opt.data_type == "create_param"
    assert opt.real_option == ""


def test_base_option_custom_values() -> None:
    opt = BigBlueButtonOption(
        option="record",
        translation="Aufzeichnung",
        value="true",
        default="false",
        parameter_type="custom",
        data_type="update_param",
        real_option="recording",
    )

    assert opt.value == "true"
    assert opt.default == "false"
    assert opt.parameter_type == "custom"
    assert opt.data_type == "update_param"
    assert opt.real_option == "recording"


def test_string_option_defaults() -> None:
    opt = BigBlueButtonOptionStr(
        option="welcome",
        translation="Begrüßung",
    )

    assert opt.value is None
    assert opt.default == ""


def test_string_option_values() -> None:
    opt = BigBlueButtonOptionStr(
        option="welcome", translation="Begrüßung", value="Hallo", default="Hi"
    )

    assert opt.value == "Hallo"
    assert opt.default == "Hi"


def test_bool_option_defaults() -> None:
    opt = BigBlueButtonOptionBool(
        option="record",
        translation="Aufzeichnung",
    )

    assert opt.value is None
    assert opt.default is False


def test_bool_option_values() -> None:
    opt = BigBlueButtonOptionBool(
        option="record", translation="Aufzeichnung", value=True, default=True
    )

    assert opt.value is True
    assert opt.default is True


def test_list_option_defaults() -> None:
    opt = BigBlueButtonOptionList(
        option="lang",
        translation="Sprache",
    )

    assert opt.value is None
    assert opt.default == ""
    assert opt.list == {}


def test_list_option_with_values() -> None:
    opt = BigBlueButtonOptionList(
        option="lang",
        translation="Sprache",
        value="de",
        default="en",
        list={"de": "Deutsch", "en": "English"},
    )

    assert opt.value == "de"
    assert opt.default == "en"
    assert opt.list["de"] == "Deutsch"


def test_asdict_conversion() -> None:
    opt = BigBlueButtonOptionStr(option="welcome", translation="Begrüßung", value="Hallo")

    data = asdict(opt)

    assert isinstance(data, dict)
    assert data["option"] == "welcome"
    assert data["value"] == "Hallo"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("false", False),
        ("0", False),
        ("random", False),
        ("", False),
    ],
)
def test_parse_boolean_option(value: str, expected: bool) -> None:
    assert parse_boolean_option(value) is expected


def test_flatten_params_str_bool_list() -> None:
    options = [
        BigBlueButtonOption(option="a", value="hello", data_type="str", real_option=""),
        BigBlueButtonOption(option="b", value="true", data_type="bool", real_option=""),
        BigBlueButtonOption(option="c", value="x", data_type="list", real_option=""),
    ]

    result = flatten_params(options)

    assert result["a"] == "hello"
    assert result["b"] is True
    assert result["c"] == "x"


def test_flatten_params_real_option_override() -> None:
    options = [
        BigBlueButtonOption(option="a", value="hello", data_type="str", real_option="real_a"),
    ]

    result = flatten_params(options)

    assert "a" not in result
    assert result["real_a"] == "hello"


def test_flatten_params_missing_value_defaults() -> None:
    options = [
        BigBlueButtonOption(option="a", data_type="str", real_option=""),
        BigBlueButtonOption(option="b", data_type="bool", real_option=""),
    ]

    result = flatten_params(options)

    assert result["a"] == ""
    assert result["b"] is False


def test_create_model_from_option_found(monkeypatch: MonkeyPatch) -> None:
    fake_option = SimpleNamespace(
        option="test", data_type="str", parameter_type="create_param", real_option="real"
    )

    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.KnownBigBlueButtonOptions",
        [fake_option],
    )

    result = create_model_from_option(1, "test")

    assert result is not None
    assert result.realm_id == 1
    assert result.option == "test"
    assert result.data_type == "str"
    assert result.parameter_type == "create_param"
    assert result.real_option == "real"


def test_create_model_from_option_not_found(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.KnownBigBlueButtonOptions",
        [],
    )

    result = create_model_from_option(1, "unknown")

    assert result is None


def test_update_existing_option(monkeypatch: MonkeyPatch) -> None:
    saved = {}

    class FakeObj:
        def __init__(self) -> None:
            self.value = None

        def save(self) -> None:
            saved["called"] = True

    fake_instance = FakeObj()

    class FakeQuerySet:
        def filter(self, **kwargs: Any) -> Self:
            return self

        def last(self) -> object:
            return fake_instance

    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.RealmBigBlueButton.objects", FakeQuerySet()
    )

    update_big_blue_button_option(1, "opt", "123")

    assert fake_instance.value == "123"
    assert saved["called"] is True


def test_update_creates_if_missing(monkeypatch: MonkeyPatch) -> None:
    created = {}

    class FakeObj:
        def __init__(self) -> None:
            self.value = None

        def save(self) -> None:
            created["saved"] = True

    class FakeQuerySet:
        def filter(self, **kwargs: Any) -> Self:
            return self

        def last(self) -> None:
            return None

    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.RealmBigBlueButton.objects", FakeQuerySet()
    )
    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.create_model_from_option", lambda **kwargs: FakeObj()
    )

    update_big_blue_button_option(1, "opt", True)

    assert created["saved"] is True


def test_update_raises_if_cannot_create(monkeypatch: MonkeyPatch) -> None:
    class FakeQuerySet:
        def filter(self, **kwargs: Any) -> Self:
            return self

        def last(self) -> None:
            return None

    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.RealmBigBlueButton.objects", FakeQuerySet()
    )
    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.create_model_from_option", lambda **kwargs: None
    )

    with pytest.raises(ValueError):
        update_big_blue_button_option(1, "opt", "x")


def test_merge_defaults_adds_missing(monkeypatch: MonkeyPatch) -> None:
    default = SimpleNamespace(option="a", translation="A")

    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.KnownBigBlueButtonOptions",
        [default],
    )

    class FakeQuery:
        def filter(self, **kwargs: Any) -> Self:
            return self

        def all(self) -> list[Any]:
            return []

    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.RealmBigBlueButton.objects", FakeQuery()
    )

    result = merge_big_blue_button_options_defaults(1)

    assert result == [default]


def test_merge_defaults_merges_existing(monkeypatch: MonkeyPatch) -> None:
    default = SimpleNamespace(option="a", translation="A")

    existing = SimpleNamespace(option="a", translation="", data_type="str")

    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.KnownBigBlueButtonOptions",
        [default],
    )

    class FakeQuery:
        def filter(self, **kwargs: Any) -> Self:
            return self

        def all(self) -> list[Any]:
            return [existing]

    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.RealmBigBlueButton.objects", FakeQuery()
    )

    result = merge_big_blue_button_options_defaults(1)

    assert result[0] == existing
    assert existing.translation == "A"


def test_get_all_options_str(monkeypatch: MonkeyPatch) -> None:
    fake = BigBlueButtonOptionStr(
        id=1,
        option="a",
        value="hello",
        data_type="str",
        translation="A",
        real_option="",
    )

    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.merge_big_blue_button_options_defaults",
        lambda realm_id: [fake],
    )

    result = get_all_big_blue_button_options_uncached(1)

    assert isinstance(result, BigBlueButtonOptionStr)
    assert result["a"].value == "hello"


def test_get_all_options_bool(monkeypatch: MonkeyPatch) -> None:
    fake = BigBlueButtonOptionBool(
        id=1,
        option="b",
        value=True,
        data_type="bool",
        translation="B",
        real_option="",
    )

    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.merge_big_blue_button_options_defaults",
        lambda realm_id: [fake],
    )

    result = get_all_big_blue_button_options_uncached(1)

    assert result["b"].value is True


def test_get_all_options_list(monkeypatch: MonkeyPatch) -> None:
    fake = BigBlueButtonOptionList(
        id=1,
        option="c",
        value="x",
        data_type="list",
        translation="C",
        list={"x": "X"},
        real_option="",
    )

    monkeypatch.setattr(
        "zerver.models.realm_big_blue_button.merge_big_blue_button_options_defaults",
        lambda realm_id: [fake],
    )

    result = get_all_big_blue_button_options_uncached(1)

    option = result["c"]
    assert isinstance(option, BigBlueButtonOptionList)
    assert option.list == {"x": "X"}
