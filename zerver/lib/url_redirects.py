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
    URLRedirect("/help/pm-mention-alert-notifications", "/help/dm-mention-alert-notifications"),
    URLRedirect("/help/restrict-private-messages", "/help/restrict-direct-messages"),
    URLRedirect("/help/reading-pms", "/help/reading-dms"),
    URLRedirect("/help/private-messages", "/help/direct-messages"),
    URLRedirect("/help/configure-who-can-edit-topics", "/help/restrict-moving-messages"),
    URLRedirect(
        "/help/configure-message-editing-and-deletion",
        "/help/restrict-message-editing-and-deletion",
    ),
    URLRedirect("/help/restrict-visibility-of-email-addresses", "/help/configure-email-visibility"),
    URLRedirect("/help/change-default-view", "/help/configure-default-view"),
    URLRedirect("/help/recent-topics", "/help/recent-conversations"),
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
    URLRedirect("/help/delete-a-stream", "/help/archive-a-channel"),
    URLRedirect("/help/archive-a-stream", "/help/archive-a-channel"),
    URLRedirect("/help/change-the-topic-of-a-message", "/help/rename-a-topic"),
    URLRedirect("/help/configure-missed-message-emails", "/help/email-notifications"),
    URLRedirect("/help/add-an-alert-word", "/help/dm-mention-alert-notifications#alert-words"),
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
    # The `help/about-streams-and-topics` and `help/streams-and-topics` redirects are particularly
    # important, because the old URLs appear in links from Welcome Bot messages.
    URLRedirect("/help/about-streams-and-topics", "/help/channels-and-topics"),
    URLRedirect("/help/streams-and-topics", "/help/channels-and-topics"),
    URLRedirect("/help/community-topic-edits", "/help/restrict-moving-messages"),
    URLRedirect(
        "/help/only-allow-admins-to-add-emoji", "/help/custom-emoji#change-who-can-add-custom-emoji"
    ),
    URLRedirect(
        "/help/configure-who-can-add-custom-emoji",
        "/help/custom-emoji#change-who-can-add-custom-emoji",
    ),
    URLRedirect("/help/add-custom-emoji", "/help/custom-emoji"),
    URLRedirect("/help/night-mode", "/help/dark-theme"),
    URLRedirect("/help/enable-emoticon-translations", "/help/configure-emoticon-translations"),
    URLRedirect("/help/web-public-streams", "/help/public-access-option"),
    URLRedirect("/help/starting-a-new-private-thread", "/help/starting-a-new-direct-message"),
    URLRedirect("/help/edit-or-delete-a-message", "/help/delete-a-message"),
    URLRedirect("/help/start-a-new-topic", "/help/starting-a-new-topic"),
    URLRedirect("/help/configure-default-view", "/help/configure-home-view"),
    URLRedirect("/help/reading-topics", "/help/reading-conversations"),
    URLRedirect("/help/finding-a-topic-to-read", "/help/finding-a-conversation-to-read"),
    URLRedirect("/help/view-and-browse-images", "/help/view-images-and-videos"),
    URLRedirect("/help/bots-and-integrations", "/help/bots-overview"),
    URLRedirect("/help/configure-notification-bot", "/help/configure-automated-notices"),
    URLRedirect("/help/all-messages", "/help/combined-feed"),
    URLRedirect("/help/create-streams", "/help/create-channels"),
    URLRedirect("/help/create-a-stream", "/help/create-a-channel"),
    URLRedirect("/help/message-a-stream-by-email", "/help/message-a-channel-by-email"),
    URLRedirect("/help/browse-and-subscribe-to-streams", "/help/browse-and-subscribe-to-channels"),
    URLRedirect("/help/unsubscribe-from-a-stream", "/help/unsubscribe-from-a-channel"),
    URLRedirect("/help/view-stream-subscribers", "/help/view-channel-subscribers"),
    URLRedirect(
        "/help/add-or-remove-users-from-a-stream", "/help/add-or-remove-users-from-a-channel"
    ),
    URLRedirect("/help/pin-a-stream", "/help/pin-a-channel"),
    URLRedirect("/help/change-the-color-of-a-stream", "/help/change-the-color-of-a-channel"),
    URLRedirect("/help/move-content-to-another-stream", "/help/move-content-to-another-channel"),
    URLRedirect("/help/manage-inactive-streams", "/help/manage-inactive-channels"),
    URLRedirect("/help/stream-notifications", "/help/channel-notifications"),
    URLRedirect("/help/mute-a-stream", "/help/mute-a-channel"),
    URLRedirect(
        "/help/manage-user-stream-subscriptions", "/help/manage-user-channel-subscriptions"
    ),
    URLRedirect("/help/stream-permissions", "/help/channel-permissions"),
    URLRedirect("/help/stream-sending-policy", "/help/channel-posting-policy"),
    URLRedirect(
        "/help/configure-who-can-create-streams", "/help/configure-who-can-create-channels"
    ),
    URLRedirect(
        "/help/configure-who-can-invite-to-streams", "/help/configure-who-can-invite-to-channels"
    ),
    URLRedirect(
        "/help/set-default-streams-for-new-users", "/help/set-default-channels-for-new-users"
    ),
    URLRedirect("/help/rename-a-stream", "/help/rename-a-channel"),
    URLRedirect("/help/change-the-stream-description", "/help/change-the-channel-description"),
    URLRedirect("/help/change-the-privacy-of-a-stream", "/help/change-the-privacy-of-a-channel"),
    URLRedirect("/help/channels-and-topics", "/help/introduction-to-topics"),
    URLRedirect(
        "/help/starting-a-new-topic", "/help/introduction-to-topics#how-to-start-a-new-topic"
    ),
    URLRedirect(
        "/help/browse-and-subscribe-to-channels",
        "/help/introduction-to-channels#browse-and-subscribe-to-channels",
    ),
]

LANDING_PAGE_REDIRECTS = [
    # Add URL redirects for corporate landing pages here.
    URLRedirect("/new-user/", "/hello/"),
    URLRedirect("/developer-community/", "/development-community"),
    URLRedirect("/for/companies/", "/for/business"),
    URLRedirect("/for/working-groups-and-communities/", "/for/communities"),
]

DOCUMENTATION_REDIRECTS = (
    API_DOCUMENTATION_REDIRECTS + POLICY_DOCUMENTATION_REDIRECTS + HELP_DOCUMENTATION_REDIRECTS
)
