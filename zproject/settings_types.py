from typing import List, Optional, TypedDict


class JwtAuthKey(TypedDict):
    key: str
    # See https://pyjwt.readthedocs.io/en/latest/algorithms.html for a list
    # of supported algorithms.
    algorithms: List[str]


class SAMLIdPConfigDict(TypedDict, total=False):
    entity_id: str
    url: str
    slo_url: str
    sp_initiated_logout_enabled: bool
    attr_user_permanent_id: str
    attr_first_name: str
    attr_last_name: str
    attr_username: str
    attr_email: str
    attr_org_membership: str
    auto_signup: bool
    display_name: str
    display_icon: str
    limit_to_subdomains: List[str]
    extra_attrs: List[str]
    x509cert: str
    x509cert_path: str


class OIDCIdPConfigDict(TypedDict, total=False):
    oidc_url: str
    display_name: str
    display_icon: Optional[str]
    client_id: str
    secret: Optional[str]
    auto_signup: bool


class SCIMConfigDict(TypedDict, total=False):
    bearer_token: str
    scim_client_name: str
    name_formatted_included: bool
    create_guests_without_streams: bool
