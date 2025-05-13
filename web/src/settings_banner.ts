import $ from "jquery";

import * as banners from "./banners.ts";
import type {Banner} from "./banners.ts";
import {$t} from "./i18n.ts";
import * as settings_data from "./settings_data.ts";

const UPGRADE_ACCESS_BANNER: Banner = {
    intent: "info",
    label: $t({defaultMessage: "Available on Zulip Cloud Standard."}),
    buttons: [
        {
            label: $t({defaultMessage: "Upgrade to access"}),
            custom_classes: "request-upgrade",
            attention: "quiet",
        },
    ],
    close_button: false,
};

const UPGRADE_BANNER: Banner = {
    intent: "neutral",
    label: $t({defaultMessage: "Available on Zulip Cloud Standard."}),
    buttons: [],
    close_button: false,
};

const UPGRADE_OR_SPONSORSHIP_BANNER: Banner = {
    intent: "info",
    label: $t({
        defaultMessage: "Available on Zulip Cloud Standard.",
    }),
    buttons: [
        {
            label: $t({defaultMessage: "Upgrade"}),
            custom_classes: "request-upgrade",
            attention: "quiet",
        },
        {
            label: $t({defaultMessage: "Request sponsorship"}),
            custom_classes: "request-sponsorship",
            attention: "borderless",
        },
    ],
    close_button: false,
};

const SPONSORSHIP_BANNER: Banner = {
    intent: "neutral",
    label: $t({defaultMessage: "Available on Zulip Cloud Standard."}),
    buttons: [],
    close_button: false,
};

const GROUP_INFO_BANNER: Banner = {
    intent: "info",
    label: $t({
        defaultMessage:
            "User groups offer a flexible way to manage permissions in your organization.",
    }),
    buttons: [
        {
            label: $t({defaultMessage: "Learn more"}),
            custom_classes: "user-groups-info",
            attention: "quiet",
        },
    ],
    close_button: false,
};

const STREAM_INFO_BANNER: Banner = {
    intent: "info",
    label: $t({
        defaultMessage: "Channels organize conversations based on who needs to see them.",
    }),
    buttons: [
        {
            label: $t({defaultMessage: "Learn more"}),
            custom_classes: "stream-info",
            attention: "quiet",
        },
    ],
    close_button: false,
};

const MOBILE_PUSH_NOTIFICATION_BANNER: Banner = {
    intent: "warning",
    label: $t({
        defaultMessage: "Mobile push notifications are not enabled on this server.",
    }),
    buttons: [
        {
            label: $t({defaultMessage: "Learn more"}),
            custom_classes: "mobile-push-notification-info",
            attention: "quiet",
        },
    ],
    close_button: false,
};

function initialize_upgrade_banners(): void {
    const has_billing_access = settings_data.user_has_billing_access();
    const $org_upgrade_container = $(".organization-upgrade-banners-container");
    if ($org_upgrade_container.length > 0 && has_billing_access) {
        banners.open(UPGRADE_ACCESS_BANNER, $org_upgrade_container);
    } else {
        banners.open(UPGRADE_BANNER, $org_upgrade_container);
    }

    const $upgrade_or_sponsership_container = $(".upgrade-or-sponsorship-banners-container");
    if ($upgrade_or_sponsership_container.length > 0 && has_billing_access) {
        banners.open(UPGRADE_OR_SPONSORSHIP_BANNER, $upgrade_or_sponsership_container);
    } else {
        banners.open(SPONSORSHIP_BANNER, $upgrade_or_sponsership_container);
    }

    const $group_info_container = $(".group-info-banner");
    if ($group_info_container.length > 0) {
        banners.open(GROUP_INFO_BANNER, $group_info_container);
    }

    const $stream_info_container = $(".stream-info-banner");
    if ($stream_info_container.length > 0) {
        banners.open(STREAM_INFO_BANNER, $stream_info_container);
    }

    const $mobile_push_notification_container = $(".mobile-push-notifications-banner-container");
    if ($mobile_push_notification_container.length > 0) {
        banners.open(MOBILE_PUSH_NOTIFICATION_BANNER, $mobile_push_notification_container);
    }
}

export function set_up(): void {
    $(document).on("click", ".request-upgrade", (e) => {
        e.preventDefault();
        window.open("/upgrade/", "_blank", "noopener,noreferrer");
    });

    $(document).on("click", ".request-sponsorship", (e) => {
        e.preventDefault();
        window.open("/sponsorship/", "_blank", "noopener,noreferrer");
    });

    $(document).on("click", ".user-groups-info", (e) => {
        e.preventDefault();
        window.open("/help/user-groups", "_blank", "noopener,noreferrer");
    });

    $(document).on("click", ".stream-info", (e) => {
        e.preventDefault();
        window.open("/help/introduction-to-channels", "_blank", "noopener,noreferrer");
    });

    $(document).on("click", ".mobile-push-notification-info", (e) => {
        e.preventDefault();
        window.open(
            "/help/mobile-notifications#enabling-push-notifications-for-self-hosted-servers",
            "_blank",
            "noopener,noreferrer",
        );
    });

    initialize_upgrade_banners();
}
