// @ts-check

import * as fs from "node:fs";

import starlight from "@astrojs/starlight";
import {defineConfig, envField} from "astro/config";
import compressor from "astro-compressor";
import Icons from "unplugin-icons/vite";

/**
 * @returns {import("vite").PluginOption}
 */
function createRedirectPlugin() {
    const proxyPort = process.env.ZULIP_WEB_APP_PROXY_PORT || "9991";
    // Astro and starlight middlewares run after astro's vite middleware,
    // which gives error before our logic here could run, so the only option
    // left with us was to use a vite plugin.
    return {
        name: "redirect-plugin",
        enforce: "post",
        /**
         * configureServer only runs in development mode, we handle the redirects
         * in production using nginx.
         * @param {import("vite").ViteDevServer} server
         */
        configureServer(server) {
            return () => {
                // The method exposed by the connect app at server.middlewares is `use`.
                // But `use` appends our middleware at the end of the stack, before which
                // the trailingSlashMiddleware of astro runs and gives an error before it
                // can reach our middleware. `stack.unshift` ensures our middleware runs
                // first.
                server.middlewares.stack.unshift({
                    route: "",
                    /**
                     * @param {import("http").IncomingMessage} req
                     * @param {import("http").ServerResponse} res
                     * @param {Function} next
                     */
                    handle(req, res, next) {
                        // Canonical URL for the root of the help center is /help/,
                        // but for all other help URLs, there should be no trailingSlash.
                        // We have set trailingSlash to never in astro. Setting it to ignore
                        // will make our /help/ work, but it causes sidebar and other
                        // components to generate links with a trailingSlash at the end. So
                        // we manually handle this case.
                        if (req.url === "/help/") {
                            req.url = "/help";
                        }

                        // Help center dev server always runs on a port different than
                        // the web app. We have relative URLs pointing to the web app
                        // in the help center, but they are not on the port help center
                        // is running on. We redirect here to our web app proxy port.
                        if (req.url && !req.url.startsWith("/help")) {
                            const host = req.headers.host || "localhost";
                            const redirectUrl = new URL(req.url, `http://${host}`);
                            redirectUrl.port = proxyPort;
                            res.writeHead(302, {Location: redirectUrl.toString()});
                            res.end();
                            return;
                        }

                        next();
                    },
                });
            };
        },
    };
}

// https://astro.build/config
export default defineConfig({
    base: "help",
    trailingSlash: "never",
    vite: {
        plugins: [
            // eslint-disable-next-line new-cap
            Icons({
                compiler: "astro",
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
                iconCustomizer(collection, icon, props) {
                    if (collection === "zulip-icon" || collection === "fa") {
                        // We need to override some default starlight behaviour to make
                        // icons look nice, see the css for this class to see the reasoning
                        // for each individual override of the default css.
                        props.class = "zulip-unplugin-icon";

                        if (collection === "zulip-icon" && icon.startsWith("user-circle-")) {
                            const iconSuffix = icon.replace("user-circle-", "");
                            props.class = `zulip-unplugin-icon user-circle user-circle-${iconSuffix}`;
                        }
                    }
                },
            }),
            createRedirectPlugin(),
        ],
        ssr: {
            noExternal: ["zod"],
        },
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
        compressor({
            gzip: true,
            brotli: false,
            zstd: false,
        }),
        starlight({
            title: "Zulip help center",
            favicon: "../static/images/favicon.svg",
            components: {
                Footer: "./src/components/Footer.astro",
                Head: "./src/components/Head.astro",
            },
            pagination: false,
            routeMiddleware: "./src/route_data.ts",
            customCss: ["./src/styles/main.css"],
            sidebar: [
                {
                    label: "Zulip homepage",
                    link: "https://zulip.com",
                    attrs: {
                        class: "external-icon-sidebar",
                        target: "_blank",
                        rel: "noopener noreferrer",
                    },
                },
                {
                    label: "Help center home",
                    slug: "index",
                },
                {
                    label: "Guides for getting started",
                    items: [
                        {
                            label: "Getting started",
                            link: "/getting-started-with-zulip",
                        },
                        {
                            label: "Choosing a team chat app",
                            link: "https://blog.zulip.com/2024/11/04/choosing-a-team-chat-app/",
                            attrs: {
                                class: "external-icon-sidebar",
                                target: "_blank",
                                rel: "noopener noreferrer",
                            },
                        },
                        {
                            label: "Why Zulip",
                            link: "https://zulip.com/why-zulip/",
                            attrs: {
                                class: "external-icon-sidebar",
                                target: "_blank",
                                rel: "noopener noreferrer",
                            },
                        },
                        "trying-out-zulip",
                        {
                            label: "Zulip Cloud or self-hosting?",
                            link: "/zulip-cloud-or-self-hosting",
                        },
                        "moving-to-zulip",
                        "moderating-open-organizations",
                        "setting-up-zulip-for-a-class",
                        "using-zulip-for-a-class",
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
                        "protect-your-account",
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
                    label: "Guides for mastering Zulip",
                    items: [
                        "keyboard-shortcuts",
                        "reading-strategies",
                        "mastering-the-compose-box",
                        "format-your-message-using-markdown",
                        {
                            label: "Search filters",
                            link: "/search-for-messages/#search-filters",
                        },
                        "using-zulip-via-email",
                    ],
                },
                {
                    label: "Writing messages",
                    items: [
                        "format-your-message-using-markdown",
                        "mention-a-user-or-group",
                        {
                            label: "Link to a channel, topic or message",
                            link: "/link-to-a-message-or-conversation",
                        },
                        "format-a-quote",
                        "quote-or-forward-a-message",
                        "emoji-and-emoticons",
                        "insert-a-link",
                        "saved-snippets",
                        "share-and-upload-files",
                        {
                            label: "Animated GIFs",
                            link: "/animated-gifs-from-giphy",
                        },
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
                        {
                            label: "Preview messages before sending",
                            link: "/preview-your-message-before-sending",
                        },
                        {
                            label: "Verify a message was sent",
                            link: "/verify-your-message-was-successfully-sent",
                        },
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
                        {
                            label: "Configure where you land",
                            link: "/configure-where-you-land",
                        },
                        "emoji-reactions",
                        "view-your-mentions",
                        "star-a-message",
                        "schedule-a-reminder",
                        "view-images-and-videos",
                        "view-messages-sent-by-a-user",
                        "link-to-a-message-or-conversation",
                        "search-for-messages",
                        "printing-messages",
                        {
                            label: "View message content as Markdown",
                            link: "/view-the-markdown-source-of-a-message",
                        },
                        {
                            label: "View when message was sent",
                            link: "/view-the-exact-time-a-message-was-sent",
                        },
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
                        "channel-folders",
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
                        {
                            label: "Do Not Disturb",
                            link: "/do-not-disturb",
                        },
                    ],
                },
                {
                    label: "Apps",
                    items: [
                        {
                            label: "Download apps",
                            link: "https://zulip.com/apps/",
                            attrs: {
                                class: "external-icon-sidebar",
                                target: "_blank",
                                rel: "noopener noreferrer",
                            },
                        },
                        {
                            label: "Mobile app installation guides",
                            link: "/mobile-app-install-guide",
                        },
                        {
                            label: "Desktop installation guides",
                            link: "/desktop-app-install-guide",
                        },
                        "supported-browsers",
                        {
                            label: "Configure how links open",
                            link: "/configure-how-links-open",
                        },
                        "connect-through-a-proxy",
                        "custom-certificates",
                    ],
                },
                {
                    label: "Zulip administration",
                    link: "#",
                    attrs: {
                        class: "non-clickable-sidebar-heading",
                    },
                },
                {
                    label: "Organization profile",
                    items: [
                        "organization-type",
                        {
                            label: "Communities directory",
                            link: "/communities-directory",
                        },
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
                        {
                            label: "Configure default new user settings",
                            link: "/configure-default-new-user-settings",
                        },
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
                    label: "Channel management",
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
                        "manage-channel-folders",
                        "channel-permissions",
                        "channel-posting-policy",
                        "configure-who-can-administer-a-channel",
                        "configure-who-can-create-channels",
                        {
                            label: "Configure who can subscribe",
                            link: "/configure-who-can-subscribe",
                        },
                        {
                            label: "Configure who can subscribe others",
                            link: "/configure-who-can-invite-to-channels",
                        },
                        {
                            label: "Configure who can unsubscribe anyone",
                            link: "/configure-who-can-unsubscribe-others",
                        },
                        "subscribe-users-to-a-channel",
                        "unsubscribe-users-from-a-channel",
                        "set-default-channels-for-new-users",
                        "rename-a-channel",
                        "change-the-channel-description",
                        "pin-information",
                        "change-the-privacy-of-a-channel",
                        {
                            label: "Delete or archive a channel",
                            link: "/archive-a-channel",
                        },
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
                        {
                            label: "Restrict message editing",
                            link: "/restrict-message-editing-and-deletion",
                        },
                        "restrict-message-edit-history-access",
                        "restrict-moving-messages",
                        "restrict-resolving-topics",
                        "restrict-name-and-email-changes",
                        "restrict-profile-picture-changes",
                        "restrict-permissions-of-new-members",
                    ],
                },
                {
                    label: "Organization settings",
                    items: [
                        {
                            label: "Configure organization language",
                            link: "/configure-organization-language",
                        },
                        "custom-emoji",
                        "configure-call-provider",
                        "add-a-custom-linkifier",
                        {
                            label: "Require topics in channel messages",
                            link: "/require-topics",
                        },
                        "image-video-and-website-previews",
                        "hide-message-content-in-emails",
                        "message-retention-policy",
                        "digest-emails",
                        "disable-welcome-emails",
                        "configure-a-custom-welcome-message",
                        "configure-automated-notices",
                        "configure-multi-language-search",
                        "analytics",
                    ],
                },
                {
                    label: "Bots & integrations",
                    items: [
                        "bots-overview",
                        "integrations-overview",
                        "add-a-bot-or-integration",
                        {
                            label: "Generate integration URL",
                            link: "/generate-integration-url",
                        },
                        "manage-a-bot",
                        "deactivate-or-reactivate-a-bot",
                        "request-an-integration",
                        {
                            label: "Restrict bot creation",
                            link: "/restrict-bot-creation",
                        },
                        "view-your-bots",
                        "view-all-bots-in-your-organization",
                    ],
                },
                {
                    label: "Support",
                    items: [
                        "view-zulip-version",
                        "zulip-cloud-billing",
                        {
                            label: "Self-hosted billing",
                            link: "/self-hosted-billing",
                        },
                        "gdpr-compliance",
                        {
                            label: "Move to Zulip Cloud",
                            link: "/move-to-zulip-cloud",
                        },
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
    // Redirects in astro are just directories with index.html inside
    // them doing the redirect we define in the value. The base of
    // /help/ will apply to the keys in the list below but we will
    // have to prepend /help/ in the redirect URL.
    redirects: {
        "pm-mention-alert-notifications": "/help/dm-mention-alert-notifications",
        "restrict-private-messages": "/help/restrict-direct-messages",
        "reading-pms": "/help/direct-messages",
        "private-messages": "/help/direct-messages",
        "configure-who-can-edit-topics": "/help/restrict-moving-messages",
        "configure-message-editing-and-deletion": "/help/restrict-message-editing-and-deletion",
        "restrict-visibility-of-email-addresses": "/help/configure-email-visibility",
        "change-default-view": "/help/configure-default-view",
        "recent-topics": "/help/recent-conversations",
        "add-custom-profile-fields": "/help/custom-profile-fields",
        "enable-enter-to-send": "/help/configure-send-message-keys",
        "change-the-default-language-for-your-organization":
            "/help/configure-organization-language",
        "delete-a-stream": "/help/archive-a-channel",
        "archive-a-stream": "/help/archive-a-channel",
        "change-the-topic-of-a-message": "/help/rename-a-topic",
        "configure-missed-message-emails": "/help/email-notifications",
        "add-an-alert-word": "/help/dm-mention-alert-notifications#alert-words",
        "test-mobile-notifications": "/help/mobile-notifications",
        "troubleshooting-desktop-notifications":
            "/help/desktop-notifications#troubleshooting-desktop-notifications",
        "change-notification-sound": "/help/desktop-notifications#change-notification-sound",
        "configure-message-notification-emails": "/help/email-notifications",
        "disable-new-login-emails": "/help/email-notifications#new-login-emails",
        // The `help/about-streams-and-topics` and `help/streams-and-topics` redirects are particularly
        // important, because the old URLs appear in links from Welcome Bot messages.
        "about-streams-and-topics": "/help/introduction-to-topics",
        "streams-and-topics": "/help/introduction-to-topics",
        "community-topic-edits": "/help/restrict-moving-messages",
        "only-allow-admins-to-add-emoji": "/help/custom-emoji#change-who-can-add-custom-emoji",
        "configure-who-can-add-custom-emoji": "/help/custom-emoji#change-who-can-add-custom-emoji",
        "add-custom-emoji": "/help/custom-emoji",
        "night-mode": "/help/dark-theme",
        "enable-emoticon-translations": "/help/configure-emoticon-translations",
        "web-public-streams": "/help/public-access-option",
        "starting-a-new-private-thread": "/help/starting-a-new-direct-message",
        "edit-or-delete-a-message": "/help/delete-a-message",
        "start-a-new-topic": "/help/starting-a-new-topic",
        "configure-default-view": "/help/configure-home-view",
        "reading-topics": "/help/reading-conversations",
        "finding-a-topic-to-read": "/help/finding-a-conversation-to-read",
        "view-and-browse-images": "/help/view-images-and-videos",
        "bots-and-integrations": "/help/bots-overview",
        "configure-notification-bot": "/help/configure-automated-notices",
        "all-messages": "/help/combined-feed",
        "create-streams": "/help/create-channels",
        "create-a-stream": "/help/create-a-channel",
        "message-a-stream-by-email": "/help/message-a-channel-by-email",
        "browse-and-subscribe-to-streams": "/help/browse-and-subscribe-to-channels",
        "unsubscribe-from-a-stream": "/help/unsubscribe-from-a-channel",
        "view-stream-subscribers": "/help/view-channel-subscribers",
        "add-or-remove-users-from-a-stream": "/help/subscribe-users-to-a-channel",
        "pin-a-stream": "/help/pin-a-channel",
        "change-the-color-of-a-stream": "/help/change-the-color-of-a-channel",
        "move-content-to-another-stream": "/help/move-content-to-another-channel",
        "manage-inactive-streams": "/help/manage-inactive-channels",
        "stream-notifications": "/help/channel-notifications",
        "mute-a-stream": "/help/mute-a-channel",
        "manage-user-stream-subscriptions": "/help/manage-user-channel-subscriptions",
        "stream-permissions": "/help/channel-permissions",
        "stream-sending-policy": "/help/channel-posting-policy",
        "configure-who-can-create-streams": "/help/configure-who-can-create-channels",
        "configure-who-can-invite-to-streams": "/help/configure-who-can-invite-to-channels",
        "set-default-streams-for-new-users": "/help/set-default-channels-for-new-users",
        "rename-a-stream": "/help/rename-a-channel",
        "change-the-stream-description": "/help/change-the-channel-description",
        "change-the-privacy-of-a-stream": "/help/change-the-privacy-of-a-channel",
        "channels-and-topics": "/help/introduction-to-topics",
        "starting-a-new-topic": "/help/introduction-to-topics#how-to-start-a-new-topic",
        "browse-and-subscribe-to-channels":
            "/help/introduction-to-channels#browse-and-subscribe-to-channels",
        "allow-image-link-previews": "/help/image-video-and-website-previews",
        "getting-your-organization-started-with-zulip": "/help/moving-to-zulip",
        "quote-and-reply": "/help/quote-or-forward-a-message",
        "change-a-users-role": "/help/user-roles",
        "roles-and-permissions": "/help/user-roles",
        "add-or-remove-users-from-a-channel": "/help/subscribe-users-to-a-channel",
        "disable-message-edit-history": "/help/restrict-message-edit-history-access",
        "edit-a-bot": "/help/manage-a-bot",
        "reading-dms": "/help/direct-messages",
    },
});
