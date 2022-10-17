from dataclasses import dataclass
from typing import List


@dataclass
class URLRedirect:
    old_url: str
    new_url: str


API_DOCUMENTATION_REDIRECTS: List[URLRedirect] = [
    # Add URL redirects for REST API documentation here:
    URLRedirect("/api/delete-stream", "/api/archive-stream"),
]

POLICY_DOCUMENTATION_REDIRECTS: List[URLRedirect] = [
    # Add URL redirects for policy documentation here:
    URLRedirect("/privacy/", "/policies/privacy"),
    URLRedirect("/terms/", "/policies/terms"),
]

HELP_DOCUMENTATION_REDIRECTS: List[URLRedirect] = [
    # Add URL redirects for help center documentation here:
    URLRedirect(
        "/help/add-custom-profile-fields",
        "/help/custom-profile-fields",
    ),
    URLRedirect(
        "/help/enable-enter-to-send",
        "/help/mastering-the-compose-box#toggle-between-ctrl-enter-and-enter-to-send-a-message",
    ),
    URLRedirect(
        "/help/change-the-default-language-for-your-organization",
        "/help/configure-organization-language",
    ),
    URLRedirect("/help/delete-a-stream", "/help/archive-a-stream"),
    URLRedirect("/help/change-the-topic-of-a-message", "/help/rename-a-topic"),
    URLRedirect("/help/configure-missed-message-emails", "/help/email-notifications"),
    URLRedirect("/help/add-an-alert-word", "/help/pm-mention-alert-notifications#alert-words"),
    URLRedirect("/help/test-mobile-notifications", "/help/mobile-notifications"),
    URLRedirect(
        "/help/troubleshooting-desktop-notifications",
        "/help/desktop-notifications#troubleshooting-desktop-notifications",
    ),
    URLRedirect(
        "/help/change-notification-sound", "/help/desktop-notifications#change-notification-sound"
    ),
    URLRedirect("/help/configure-message-notification-emails", "/help/email-notifications"),
    URLRedirect("/help/disable-new-login-emails", "/help/email-notifications#new-login-emails"),
    # The `help/about-streams-and-topics` redirect is particularly important,
    # because the old URL appears in links from Welcome Bot messages.
    URLRedirect("/help/about-streams-and-topics", "/help/streams-and-topics"),
    URLRedirect("/help/community-topic-edits", "/help/configure-who-can-edit-topics"),
    URLRedirect(
        "/help/only-allow-admins-to-add-emoji", "/help/custom-emoji#change-who-can-add-custom-emoji"
    ),
    URLRedirect(
        "/help/configure-who-can-add-custom-emoji",
        "/help/custom-emoji#change-who-can-add-custom-emoji",
    ),
    URLRedirect("/help/add-custom-emoji", "/help/custom-emoji"),
    URLRedirect("/help/night-mode", "/help/dark-theme"),
    URLRedirect("/help/web-public-streams", "/help/public-access-option"),
]

LANDING_PAGE_REDIRECTS = [
    # Add URL redirects for corporate landing pages here.
    URLRedirect("/new-user/", "/hello"),
    URLRedirect("/developer-community/", "/development-community"),
    URLRedirect("/for/companies/", "/for/business"),
    URLRedirect("/for/working-groups-and-communities/", "/for/communities"),
]

DOCUMENTATION_REDIRECTS = (
    API_DOCUMENTATION_REDIRECTS + POLICY_DOCUMENTATION_REDIRECTS + HELP_DOCUMENTATION_REDIRECTS
)
