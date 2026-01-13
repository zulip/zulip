from dataclasses import dataclass


@dataclass
class URLRedirect:
    old_url: str
    new_url: str


# If redirecting to the help center, we no longer test the old URL
# in the backend test suite, so it should be added to this list
# even if it was originally in the API or policies documentation.
REDIRECTED_TO_HELP_DOCUMENTATION: list[URLRedirect] = [
    URLRedirect("/api/outgoing-webhooks", "/help/outgoing-webhooks"),
    URLRedirect("/api/deploying-bots", "/help/deploying-bots"),
    URLRedirect("/api/running-bots", "/help/running-bots"),
    URLRedirect(
        "/api/writing-tests-for-interactive-bots", "/help/writing-tests-for-interactive-bots"
    ),
    URLRedirect("/api/interactive-bots-api", "/help/interactive-bots-api"),
    URLRedirect("/api/writing-bots", "/help/writing-bots"),
    URLRedirect("/api/non-webhook-integrations", "/help/non-webhook-integrations"),
    URLRedirect("/api/integrations-overview", "/help/integrations-overview"),
]

API_DOCUMENTATION_REDIRECTS: list[URLRedirect] = [
    # Add URL redirects for REST API documentation here:
    URLRedirect("/api/delete-stream", "/api/archive-stream"),
    URLRedirect(
        "/api/incoming-webhooks-overview",
        "https://zulip.readthedocs.io/en/latest/webhooks/incoming-webhooks-overview.html",
    ),
    URLRedirect(
        "/api/incoming-webhooks-walkthrough",
        "https://zulip.readthedocs.io/en/latest/webhooks/incoming-webhooks-walkthrough.html",
    ),
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

DOCUMENTATION_REDIRECTS = (
    API_DOCUMENTATION_REDIRECTS + POLICY_DOCUMENTATION_REDIRECTS + REDIRECTED_TO_HELP_DOCUMENTATION
)

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
