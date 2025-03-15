from dataclasses import asdict, dataclass
from inspect import signature
from typing import Annotated, Any, TypeAlias, get_args

from zerver.lib.integrations import WebhookIntegration
from zerver.lib.typed_endpoint import ApiParamConfig

SettingContextT: TypeAlias = dict[str, Any]
InterfacedSettingT: TypeAlias = dict[str, SettingContextT | None]

# Encoding to make sure the queries for the interfaced
# settings are unique.
INTERFACED_SETTING_ENCODING = "Z_{param}"

MapToChannelsT: TypeAlias = Annotated[
    bool,
    ApiParamConfig(INTERFACED_SETTING_ENCODING.format(param="map_to_channels")),
]

# Keep this in sync with `state_data.integrations_interfaced_settings_schema`
# this dict is not a dataclass because Type aliases inside dataclass definitions
# are not supported at runtime.
SUPPORTED_INTERFACED_SETTINGS: dict[str, TypeAlias] = {
    "MapToChannelsT": MapToChannelsT,
}


@dataclass
class SettingContext:
    parameter_name: str
    unique_query: str

    def __init__(self, arg_name: str, arg_type: Any) -> None:
        self.parameter_name = arg_name
        api_param_config = get_args(arg_type)[1]
        assert isinstance(api_param_config, ApiParamConfig)
        whence = api_param_config.whence
        assert whence is not None
        self.unique_query = whence


def get_settings_context(arg_name: str, arg_type: Any) -> SettingContextT | None:
    settings_context = None
    if arg_type == SUPPORTED_INTERFACED_SETTINGS["MapToChannelsT"]:
        settings_context = SettingContext(arg_name, arg_type)

    if settings_context is not None:
        return asdict(settings_context)
    raise AssertionError(f"Please define a SettingContext for this setting: {arg_name}")


def get_interfaced_settings_for(
    integration: WebhookIntegration,
) -> InterfacedSettingT:
    integration_name = integration.name
    endpoint = integration.get_function()
    parameters = signature(endpoint).parameters

    known_settings: dict[Any, str] = {}
    integrations_settings: InterfacedSettingT = {}
    for name, type in SUPPORTED_INTERFACED_SETTINGS.items():
        known_settings[type] = name
        integrations_settings[name] = None

    for arg_name, arg in parameters.items():
        arg_type = arg.annotation
        if setting_name := known_settings.get(arg_type):
            if integrations_settings[setting_name] is not None:
                raise AssertionError(
                    f"Using multiple interfaced setting of the same kind is not supported. integration: {integration_name}, setting: {setting_name}"
                )
            integrations_settings[setting_name] = get_settings_context(arg_name, arg_type)

    return integrations_settings
