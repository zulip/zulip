import * as fs from "node:fs";

import starlight from "@astrojs/starlight";
import {defineConfig, envField} from "astro/config";
import Icons from "unplugin-icons/vite";

// https://astro.build/config
export default defineConfig({
    base: "help-beta",
    vite: {
        plugins: [
            // eslint-disable-next-line new-cap
            Icons({
                compiler: "astro",
                // unplugin-icons sets height and width by itself.
                // It was setting the height to 1024 and 960 for some
                // icons. It is better to set the height explicitly.
                defaultStyle:
                    "display: inline; vertical-align: text-bottom; height: 1em; width: 1em; margin-bottom: 0; margin-top: 0;",
                customCollections: {
                    // unplugin-icons has a FileSystemIconLoader which is more
                    // versatile. But it only supports one directory path for
                    // a single set of icons. We should start using that loader
                    // if they add support for multiple paths in the future.
                    async "zulip-icon"(iconName) {
                        const sharedIconsPath = `../web/shared/icons/${iconName}.svg`;
                        const webOnlyIconsPath = `../web/images/icons/${iconName}.svg`;

                        if (fs.existsSync(sharedIconsPath)) {
                            return await fs.promises.readFile(sharedIconsPath, "utf8");
                        } else if (fs.existsSync(webOnlyIconsPath)) {
                            return await fs.promises.readFile(webOnlyIconsPath, "utf8");
                        }
                        throw new Error("Zulip icon not found.");
                    },
                },
            }),
        ],
    },
    env: {
        schema: {
            SHOW_RELATIVE_LINKS: envField.boolean({
                context: "client",
                access: "public",
                optional: true,
                default: true,
            }),
            CORPORATE_ENABLED: envField.boolean({
                context: "client",
                access: "public",
                optional: true,
                default: true,
            }),
            SUPPORT_EMAIL: envField.string({
                context: "client",
                access: "public",
                optional: true,
                default: "zulip-admin@example.com",
            }),
        },
    },
    integrations: [
        starlight({
            title: "Zulip help center",
            components: {
                Footer: "./src/components/Footer.astro",
                Head: "./src/components/Head.astro",
            },
            pagination: false,
            routeMiddleware: "./src/route_data.ts",
            customCss: ["./src/styles/main.css", "./src/styles/steps.css"],
            sidebar: [
                {
                    label: "Zulip homepage",
                    link: "https://zulip.com",
                },
                {
                    label: "Help center home",
                    slug: "index",
                },
                {
                    label: "Guides",
                    items: [
                        "getting-started-with-zulip",
                        {
                            label: "Choosing a team chat app",
                            link: "https://blog.zulip.com/2024/11/04/choosing-a-team-chat-app/",
                        },
                        {
                            label: "Why Zulip",
                            link: "https://zulip.com/why-zulip/",
                        },
                        "trying-out-zulip",
                        "zulip-cloud-or-self-hosting",
                        "moving-to-zulip",
                        "moderating-open-organizations",
                        "setting-up-zulip-for-a-class",
                        "using-zulip-for-a-class",
                        "using-zulip-via-email",
                    ],
                },
                {
                    label: "Getting started",
                    items: [
                        "join-a-zulip-organization",
                        "set-up-your-account",
                        "introduction-to-topics",
                        {
                            label: "Starting a new topic",
                            link: "/introduction-to-topics#how-to-start-a-new-topic",
                        },
                        "finding-a-conversation-to-read",
                        "reading-conversations",
                        "starting-a-new-direct-message",
                        "replying-to-messages",
                        "messaging-tips",
                        "keyboard-shortcuts",
                    ],
                },
                {
                    label: "Setting up your organization",
                    items: [
                        "migrating-from-other-chat-tools",
                        "create-your-organization-profile",
                        "create-user-groups",
                        "customize-organization-settings",
                        "create-channels",
                        "customize-settings-for-new-users",
                        "invite-users-to-join",
                        "set-up-integrations",
                    ],
                },
                {
                    label: "Account basics",
                    items: [
                        "edit-your-profile",
                        "change-your-name",
                        "change-your-email-address",
                        "change-your-profile-picture",
                        "change-your-password",
                        "configure-email-visibility",
                        "logging-in",
                        "logging-out",
                        "switching-between-organizations",
                        "import-your-settings",
                        "review-your-settings",
                        "deactivate-your-account",
                    ],
                },
                {
                    label: "Preferences",
                    items: [
                        "dark-theme",
                        "font-size",
                        "line-spacing",
                        "configure-send-message-keys",
                        "change-your-language",
                        "change-your-timezone",
                        "change-the-time-format",
                        "configure-emoticon-translations",
                        "configure-home-view",
                        "enable-full-width-display",
                        "manage-your-uploaded-files",
                    ],
                },
                {
                    label: "Writing messages",
                    items: [
                        "format-your-message-using-markdown",
                        "mention-a-user-or-group",
                        "link-to-a-message-or-conversation",
                        "format-a-quote",
                        "quote-or-forward-a-message",
                        "emoji-and-emoticons",
                        "insert-a-link",
                        "saved-snippets",
                        "share-and-upload-files",
                        "animated-gifs-from-giphy",
                        "text-emphasis",
                        "paragraph-and-section-formatting",
                        "bulleted-lists",
                        "numbered-lists",
                        "tables",
                        "code-blocks",
                        "latex",
                        "spoilers",
                        "me-action-messages",
                        "create-a-poll",
                        "collaborative-to-do-lists",
                        "global-times",
                        "start-a-call",
                    ],
                },
                {
                    label: "Sending messages",
                    items: [
                        "open-the-compose-box",
                        "mastering-the-compose-box",
                        "resize-the-compose-box",
                        "typing-notifications",
                        "preview-your-message-before-sending",
                        "verify-your-message-was-successfully-sent",
                        "edit-a-message",
                        "delete-a-message",
                        "view-and-edit-your-message-drafts",
                        "schedule-a-message",
                        "message-a-channel-by-email",
                    ],
                },
                {
                    label: "Reading messages",
                    items: [
                        "reading-strategies",
                        "inbox",
                        "recent-conversations",
                        "combined-feed",
                        "channel-feed",
                        "list-of-topics",
                        "left-sidebar",
                        "message-actions",
                        "marking-messages-as-read",
                        "marking-messages-as-unread",
                        "configure-unread-message-counters",
                        "configure-where-you-land",
                        "emoji-reactions",
                        "view-your-mentions",
                        "star-a-message",
                        "schedule-a-reminder",
                        "view-images-and-videos",
                        "view-messages-sent-by-a-user",
                        "link-to-a-message-or-conversation",
                        "search-for-messages",
                        "printing-messages",
                        "view-the-markdown-source-of-a-message",
                        "view-the-exact-time-a-message-was-sent",
                        "view-a-messages-edit-history",
                        "collapse-a-message",
                        "read-receipts",
                    ],
                },
                {
                    label: "People",
                    items: [
                        "introduction-to-users",
                        "user-list",
                        "status-and-availability",
                        "user-cards",
                        "view-someones-profile",
                        "direct-messages",
                        "find-administrators",
                    ],
                },
                {
                    label: "Groups",
                    items: ["user-groups", "view-group-members"],
                },
                {
                    label: "Channels",
                    items: [
                        "introduction-to-channels",
                        {
                            label: "Subscribe to a channel",
                            link: "/introduction-to-channels#browse-and-subscribe-to-channels",
                        },
                        "create-a-channel",
                        "pin-a-channel",
                        "change-the-color-of-a-channel",
                        "unsubscribe-from-a-channel",
                        "manage-inactive-channels",
                        "move-content-to-another-channel",
                        "view-channel-information",
                        "view-channel-subscribers",
                    ],
                },
                {
                    label: "Topics",
                    items: [
                        "introduction-to-topics",
                        "rename-a-topic",
                        "resolve-a-topic",
                        "move-content-to-another-topic",
                        "general-chat-topic",
                        "delete-a-topic",
                    ],
                },
                {
                    label: "Notifications",
                    items: [
                        "channel-notifications",
                        "topic-notifications",
                        "follow-a-topic",
                        "dm-mention-alert-notifications",
                        "mute-a-channel",
                        "mute-a-topic",
                        "mute-a-user",
                        "email-notifications",
                        "desktop-notifications",
                        "mobile-notifications",
                        "do-not-disturb",
                    ],
                },
                {
                    label: "Apps",
                    items: [
                        {
                            label: "Download apps for every platform",
                            link: "https://zulip.com/apps/",
                        },
                        "mobile-app-install-guide",
                        "desktop-app-install-guide",
                        "supported-browsers",
                        "configure-how-links-open",
                        "connect-through-a-proxy",
                        "custom-certificates",
                    ],
                },
                {
                    label: "Zulip Administration",
                    link: "#",
                    attrs: {
                        class: "non-clickable-sidebar-heading",
                    },
                },
                {
                    label: "Organization profile",
                    items: [
                        "organization-type",
                        "communities-directory",
                        "linking-to-zulip",
                        "change-organization-url",
                        "deactivate-your-organization",
                    ],
                },
                {
                    label: "Import an organization",
                    items: [
                        "import-from-mattermost",
                        "import-from-slack",
                        "import-from-rocketchat",
                        "export-your-organization",
                    ],
                },
                {
                    label: "Account creation and authentication",
                    items: [
                        "configure-default-new-user-settings",
                        "custom-profile-fields",
                        "invite-new-users",
                        "restrict-account-creation",
                        "configure-authentication-methods",
                        "saml-authentication",
                        "scim",
                    ],
                },
                {
                    label: "User management",
                    items: [
                        "manage-a-user",
                        "deactivate-or-reactivate-a-user",
                        "change-a-users-name",
                        "manage-user-channel-subscriptions",
                        "manage-user-group-membership",
                    ],
                },
                {
                    label: "Channel Management",
                    items: [
                        "create-a-channel",
                        {
                            label: "Private channels",
                            link: "/channel-permissions#private-channels",
                        },
                        {
                            label: "Public channels",
                            link: "/channel-permissions#public-channels",
                        },
                        "public-access-option",
                        "general-chat-channels",
                        "channel-permissions",
                        "channel-posting-policy",
                        "configure-who-can-administer-a-channel",
                        "configure-who-can-create-channels",
                        "configure-who-can-subscribe",
                        "configure-who-can-invite-to-channels",
                        "configure-who-can-unsubscribe-others",
                        "subscribe-users-to-a-channel",
                        "unsubscribe-users-from-a-channel",
                        "set-default-channels-for-new-users",
                        "rename-a-channel",
                        "change-the-channel-description",
                        "pin-information",
                        "change-the-privacy-of-a-channel",
                        "archive-a-channel",
                    ],
                },
                {
                    label: "Permissions management",
                    items: [
                        "manage-permissions",
                        "manage-user-groups",
                        "deactivate-a-user-group",
                        "user-roles",
                        "guest-users",
                        "restrict-direct-messages",
                        "restrict-wildcard-mentions",
                        "restrict-message-editing-and-deletion",
                        "restrict-message-edit-history-access",
                        "restrict-moving-messages",
                        "restrict-resolving-topics",
                        "restrict-name-and-email-changes",
                        "restrict-profile-picture-changes",
                        "restrict-permissions-of-new-members",
                    ],
                },
                {
                    label: "Organization Settings",
                    items: [
                        "configure-organization-language",
                        "custom-emoji",
                        "configure-call-provider",
                        "add-a-custom-linkifier",
                        "require-topics",
                        "restrict-direct-messages",
                        "restrict-wildcard-mentions",
                        "restrict-moving-messages",
                        "restrict-message-editing-and-deletion",
                        "image-video-and-website-previews",
                        "hide-message-content-in-emails",
                        "message-retention-policy",
                        "digest-emails",
                        "disable-welcome-emails",
                        "configure-automated-notices",
                        "configure-multi-language-search",
                    ],
                },
                {
                    label: "Bots & Integrations",
                    items: [
                        "bots-overview",
                        "integrations-overview",
                        "add-a-bot-or-integration",
                        "generate-integration-url",
                        "manage-a-bot",
                        "deactivate-or-reactivate-a-bot",
                        "request-an-integration",
                        "restrict-bot-creation",
                        "view-your-bots",
                        "view-all-bots-in-your-organization",
                    ],
                },
                {
                    label: "Support",
                    items: [
                        "view-zulip-version",
                        "zulip-cloud-billing",
                        "self-hosted-billing",
                        "gdpr-compliance",
                        "move-to-zulip-cloud",
                        "support-zulip-project",
                        "linking-to-zulip-website",
                        "contact-support",
                    ],
                },
                {
                    label: "◀ Back to Zulip",
                    link: "../",
                },
            ],
        }),
    ],
});
