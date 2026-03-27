from collections.abc import Sequence
from dataclasses import dataclass, field

from django.db import models
from django.db.models import CASCADE

from zerver.models.realms import Realm


@dataclass(kw_only=True)
class BigBlueButtonOption:
    id: int = -1
    option: str
    translation: str
    value: str | bool | None = None
    default: str | bool | None = None
    parameter_type: str = "str"
    data_type: str = "create_param"
    real_option: str = ""


@dataclass(kw_only=True)
class BigBlueButtonOptionStr(BigBlueButtonOption):
    value: str | None = None
    default: str | None = ""


@dataclass(kw_only=True)
class BigBlueButtonOptionBool(BigBlueButtonOption):
    value: bool | None = None
    default: bool |None= False


@dataclass(kw_only=True)
class BigBlueButtonOptionList(BigBlueButtonOption):
    value: str | None = None
    default: str | None = ""
    list: dict[str, str] = field(default_factory=dict)


KnownBigBlueButtonOptions = [
    # Source: https://docs.bigbluebutton.org/development/api/#:~:text=FFFFFF.%20(added%202.0)-,muteOnStart,-Boolean
    BigBlueButtonOptionBool(
        option="mute_on_start",
        translation="realm_big_blue_button_start_muted",
        default=False,
        parameter_type="create_param",
        data_type="bool",
        real_option="muteOnStart",
    ),
    # Source: https://docs.bigbluebutton.org/development/api/#:~:text=Default%3A%20false-,guestPolicy,-Enum
    BigBlueButtonOptionList(
        option="guest_policy",
        translation="realm_big_blue_button_guest_policy",
        default="ALWAYS_ACCEPT",
        parameter_type="create_param",
        list={
            "ALWAYS_ACCEPT": "Always accept",
            "ALWAYS_DENY": "Always deny",
            "ASK_MODERATOR": "Ask moderator",
        },
        data_type="list",
        real_option="guestPolicy",
    ),
    # Source: https://docs.bigbluebutton.org/administration/customize/#:~:text=userdata%2Dbbb_skip_check_audio_on_first_join%3D
    BigBlueButtonOptionBool(
        option="skip_check_audio_on_first_join",
        translation="realm_big_blue_button_skip_check_audio_on_first_join",
        default=False,
        parameter_type="create_param",
        data_type="bool",
        real_option="userdata-bbb_skip_check_audio_on_first_join",
    ),
    # Source: https://docs.bigbluebutton.org/administration/customize/#:~:text=userdata%2Dbbb_auto_join_audio%3D
    BigBlueButtonOptionBool(
        option="auto_join_audio",
        translation="realm_big_blue_button_auto_join_audio",
        default=False,
        parameter_type="create_param",
        data_type="bool",
        real_option="userdata-bbb_auto_join_audio",
    ),
    # Source: https://docs.bigbluebutton.org/administration/customize/#:~:text=userdata%2Dbbb_listen_only_mode%3D
    BigBlueButtonOptionBool(
        option="listen_only_mode",
        translation="realm_big_blue_button_listen_only_mode",
        default=True,
        parameter_type="create_param",
        data_type="bool",
        real_option="userdata-bbb_listen_only_mode",
    ),
    # Source: https://docs.bigbluebutton.org/administration/customize/#:~:text=userdata%2Dbbb_show_session_details_on_join%3D
    BigBlueButtonOptionBool(
        option="show_session_details_on_join",
        translation="realm_big_blue_button_show_session_details_on_join",
        default=None,
        parameter_type="create_param",
        data_type="bool",
        real_option="userdata-bbb_show_session_details_on_join",
    ),
]


class RealmBigBlueButton(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)

    option = models.CharField(max_length=255, null=False, db_index=True)
    value = models.CharField(max_length=50, null=True)

    DATA_TYPES = ("str", "int", "bool", "list")
    data_type = models.CharField(default=DATA_TYPES[0], null=False, max_length=4)

    PARAMETER_TYPES = ["create_param", "join_param"]
    parameter_type = models.CharField(default=PARAMETER_TYPES[0], null=False, max_length=13)

    real_option = models.CharField(default="", null=False, max_length=100)

    translation: str = ""
    list: dict[str, str] = field(default_factory=dict)


def parse_boolean_option(value: str) -> bool:
    return value in {"true", "True", "1"}


def flatten_params(options: Sequence[RealmBigBlueButton | BigBlueButtonOption]) -> dict[str, str | bool]:  # FIX
    create_params: dict[str, str | bool] = {}
    for option in options:
        value: str | bool = ""

        if option.data_type == "str":
            value = str(getattr(option, "value", ""))  # FIX
        elif option.data_type == "bool":
            value = parse_boolean_option(str(getattr(option, "value", "")))  # FIX
        elif option.data_type == "list":
            value = str(getattr(option, "value", ""))  # FIX

        if option.real_option == "":
            create_params[option.option] = value
        else:
            create_params[option.real_option] = value

    return create_params


def get_create_params(realm_id: int) -> dict[str, str | bool]:
    return flatten_params(merge_big_blue_button_options_defaults(realm_id=realm_id, parameter_type="create_params"))


def get_join_params(realm_id: int) -> dict[str, str | bool]:
    return flatten_params(merge_big_blue_button_options_defaults(realm_id=realm_id, parameter_type="join_params"))


def create_model_from_option(realm_id: int, option: str) -> RealmBigBlueButton | None:
    for known_option in KnownBigBlueButtonOptions:
        if option == known_option.option:
            bbb_option = RealmBigBlueButton()
            bbb_option.realm_id = realm_id
            bbb_option.option = option
            bbb_option.data_type = known_option.data_type
            bbb_option.parameter_type = known_option.parameter_type
            bbb_option.real_option = known_option.real_option
            return bbb_option
    return None


def update_big_blue_button_option(realm_id: int, option: str, value: str | bool | None) -> None:
    bbb_option = RealmBigBlueButton.objects.filter(realm_id=realm_id, option=option).last()

    if bbb_option is None:
        bbb_option = create_model_from_option(realm_id=realm_id, option=option)

    if bbb_option is None:
        raise ValueError(f"BigBlueButton model for option '{option}' could not created")

    bbb_option.value = str(value)
    bbb_option.save()


def merge_big_blue_button_options_defaults(realm_id: int, parameter_type: str | None = None) -> list[RealmBigBlueButton | BigBlueButtonOption]:
    query = None
    if parameter_type is not None:
        query = RealmBigBlueButton.objects.filter(realm_id=realm_id, parameter_type=parameter_type)
    else:
        query = RealmBigBlueButton.objects.filter(realm_id=realm_id)

    bbb_options = query.all()
    options: list[RealmBigBlueButton | BigBlueButtonOption] = []

    for default_option in KnownBigBlueButtonOptions:
        option = default_option.option
        found = False

        for bbb_option in bbb_options:
            if bbb_option.option == option:
                found = True
                bbb_option.translation = default_option.translation
                if isinstance(default_option, BigBlueButtonOptionList):
                    bbb_option.list = default_option.list
                options.append(bbb_option)
                break

        if not found:
            options.append(default_option)

    return options


def get_all_big_blue_button_options_uncached(realm_id: int) -> dict[str, BigBlueButtonOption | None]:
    options: dict[str, BigBlueButtonOption | None] = {}
    bbb_options = merge_big_blue_button_options_defaults(realm_id=realm_id)

    for bbb_option in bbb_options:
        option: BigBlueButtonOption | None = None
        data_type = bbb_option.data_type

        if data_type == "str":
            option = BigBlueButtonOptionStr(
                id=bbb_option.id,
                value=str(bbb_option.value),
                option=bbb_option.option,
                data_type=data_type,
                translation=bbb_option.translation,
                real_option=bbb_option.real_option,
            )
        elif data_type == "bool":
            option = BigBlueButtonOptionBool(
                id=bbb_option.id,
                value=parse_boolean_option(str(bbb_option.value)),
                option=bbb_option.option,
                data_type=data_type,
                translation=bbb_option.translation,
                real_option=bbb_option.real_option,
            )
        elif data_type == "list":
            option = BigBlueButtonOptionList(
                id=bbb_option.id,
                value=str(bbb_option.value),
                option=bbb_option.option,
                data_type=data_type,
                translation=bbb_option.translation,
                list=getattr(bbb_option, "list", {}),
                real_option=bbb_option.real_option,
            )

        if data_type is not None:
            options[str(bbb_option.option)] = option

    return options
