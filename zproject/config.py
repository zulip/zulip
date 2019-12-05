import os
from typing import Optional, overload
import configparser

DEPLOY_ROOT = os.path.realpath(os.path.dirname(os.path.dirname(__file__)))

config_file = configparser.RawConfigParser()
config_file.read("/etc/zulip/zulip.conf")

# Whether this instance of Zulip is running in a production environment.
PRODUCTION = config_file.has_option('machine', 'deploy_type')
DEVELOPMENT = not PRODUCTION

secrets_file = configparser.RawConfigParser()
if PRODUCTION:
    secrets_file.read("/etc/zulip/zulip-secrets.conf")
else:
    secrets_file.read(os.path.join(DEPLOY_ROOT, "zproject/dev-secrets.conf"))

@overload
def get_secret(key: str, default_value: str, development_only: bool=False) -> str:
    ...
@overload
def get_secret(key: str, default_value: Optional[str]=None,
               development_only: bool=False) -> Optional[str]:
    ...
def get_secret(key: str, default_value: Optional[str]=None,
               development_only: bool=False) -> Optional[str]:
    if development_only and PRODUCTION:
        return default_value
    return secrets_file.get('secrets', key, fallback=default_value)

@overload
def get_config(section: str, key: str, default_value: str) -> str:
    ...
@overload
def get_config(section: str, key: str, default_value: Optional[str]=None) -> Optional[str]:
    ...
def get_config(section: str, key: str, default_value: Optional[str]=None) -> Optional[str]:
    return config_file.get(section, key, fallback=default_value)

def get_from_file_if_exists(path: str) -> str:
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    else:
        return ''
