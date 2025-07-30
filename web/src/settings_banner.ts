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

export function set_up_upgrade_banners(): void {
    const has_billing_access = settings_data.user_has_billing_access();
    const is_business_type_org =
        realm.realm_org_type === settings_config.all_org_type_values.business.code;
    const $upgrade_banner_containers = $(".upgrade-organization-banner-container");

    if ($upgrade_banner_containers.length === 0) {
        return;
    }

    let banner;
    if (is_business_type_org) {
        banner = has_billing_access ? UPGRADE_ACCESS_BANNER : AVAILABLE_ON_STANDARD;
    } else {
        banner = has_billing_access ? UPGRADE_OR_SPONSORSHIP_BANNER : AVAILABLE_ON_STANDARD;
    }
    banners.open(banner, $upgrade_banner_containers);
}

export function set_up_banner($container: JQuery, banner: Banner, url?: string): void {
    if ($container.length === 0) {
        return;
    }

    banners.open(banner, $container);

    if (url !== undefined) {
        $container.on("click", ".banner-external-link", (e) => {
            e.preventDefault();
            window.open(url, "_blank", "noopener,noreferrer");
        });
    }
}
