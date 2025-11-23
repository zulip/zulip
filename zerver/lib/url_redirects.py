from dataclasses import dataclass


@dataclass
class URLRedirect:
    old_url: str
    new_url: str


API_DOCUMENTATION_REDIRECTS: list[URLRedirect] = [
    # Add URL redirects for REST API documentation here:
    URLRedirect("/api/delete-stream", "/api/archive-stream"),
]

POLICY_DOCUMENTATION_REDIRECTS: list[URLRedirect] = [
    # Add URL redirects for policy documentation here:
    URLRedirect("/privacy/", "/policies/privacy"),
    URLRedirect("/terms/", "/policies/terms"),
]

LANDING_PAGE_REDIRECTS = [
    # Add URL redirects for corporate landing pages here.
    URLRedirect("/new-user/", "/hello/"),
    URLRedirect("/developer-community/", "/development-community"),
    URLRedirect("/for/companies/", "/for/business"),
    URLRedirect("/for/working-groups-and-communities/", "/for/communities"),
    URLRedirect("/try-zulip/", "https://chat.zulip.org/?show_try_zulip_modal"),
]

DOCUMENTATION_REDIRECTS = API_DOCUMENTATION_REDIRECTS + POLICY_DOCUMENTATION_REDIRECTS

# List of category slugs at the time of changing the URL scheme to have
# `/category` be appended before the category slug. This list does not
# need to change with changing categories.
INTEGRATION_CATEGORY_SLUGS = [
    "bots",
    "communication",
    "continuous-integration",
    "customer-support",
    "deployment",
    "entertainment",
    "financial",
    "hr",
    "marketing",
    "meta-integration",
    "misc",
    "monitoring",
    "productivity",
    "project-management",
    "version-control",
]


def get_integration_category_redirects() -> list[URLRedirect]:
    return [
        URLRedirect(
            f"/integrations/{slug}",
            f"/integrations/category/{slug}",
        )
        for slug in INTEGRATION_CATEGORY_SLUGS
    ]
