import $ from "jquery";

import * as banners from "./banners.ts";
import type {Banner} from "./banners.ts";
import {$t} from "./i18n.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import {realm} from "./state_data.ts";

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
    custom_classes: "organization-upgrade-banner",
    close_button: false,
};

const AVAILABLE_ON_STANDARD: Banner = {
    intent: "neutral",
    label: $t({defaultMessage: "Available on Zulip Cloud Standard."}),
    buttons: [],
    custom_classes: "organization-upgrade-banner",
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
    custom_classes: "organization-upgrade-banner",
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
    custom_classes: "mobile-push-notifications-banner",
    close_button: false,
};

export function set_up_upgrade_banners(): void {
    const has_billing_access = settings_data.user_has_billing_access();
    const is_business_type_org =
        realm.realm_org_type === settings_config.all_org_type_values.business.code;
    const $upgrade_container = $(".upgrade-organization-banner-container");

    if ($upgrade_container.length === 0) {
        return;
    }

    let banner;
    if (is_business_type_org) {
        banner = has_billing_access ? UPGRADE_ACCESS_BANNER : AVAILABLE_ON_STANDARD;
    } else {
        banner = has_billing_access ? UPGRADE_OR_SPONSORSHIP_BANNER : AVAILABLE_ON_STANDARD;
    }
    banners.open(banner, $upgrade_container);
}

export function set_up_group_info_banner(): void {
    const $container = $(".group-info-banner");
    if ($container.length === 0) {
        return;
    }

    banners.open(GROUP_INFO_BANNER, $container);

    $container.on("click", ".user-groups-info", (e) => {
        e.preventDefault();
        window.open("/help/user-groups", "_blank", "noopener,noreferrer");
    });
}

export function set_up_stream_info_banner(): void {
    const $container = $(".stream-info-banner");
    if ($container.length === 0) {
        return;
    }

    banners.open(STREAM_INFO_BANNER, $container);

    $container.on("click", ".stream-info", (e) => {
        e.preventDefault();
        window.open("/help/introduction-to-channels", "_blank", "noopener,noreferrer");
    });
}

export function set_up_mobile_push_banner(): void {
    const $container = $(".mobile-push-notifications-banner-container");
    if ($container.length === 0) {
        return;
    }

    banners.open(MOBILE_PUSH_NOTIFICATION_BANNER, $container);
}
