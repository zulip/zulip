import $ from "jquery";

import * as banners from "./banners.ts";
import type {Banner} from "./banners.ts";
import type {ActionButton} from "./buttons.ts";
import {$t} from "./i18n.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import {realm} from "./state_data.ts";

export function set_up_upgrade_banners(): void {
    const has_billing_access = settings_data.user_has_billing_access();
    const is_business_type_org =
        realm.realm_org_type === settings_config.all_org_type_values.business.code;
    const $upgrade_banner_containers = $(".upgrade-organization-banner-container");

    if ($upgrade_banner_containers.length === 0) {
        return;
    }

    let upgrade_buttons: ActionButton[] = [];
    let banner_intent: Banner["intent"] = "neutral";

    if (has_billing_access) {
        banner_intent = "info";
        upgrade_buttons = [
            {
                label: $t({defaultMessage: "Upgrade"}),
                custom_classes: "request-upgrade",
                variant: "subtle",
            },
        ];

        if (!is_business_type_org) {
            upgrade_buttons = [
                ...upgrade_buttons,
                {
                    label: $t({defaultMessage: "Request sponsorship"}),
                    custom_classes: "request-sponsorship",
                    variant: "text",
                },
            ];
        }
    }

    const upgrade_banner: Banner = {
        intent: banner_intent,
        label: $t({defaultMessage: "Available on Zulip Cloud Standard."}),
        buttons: upgrade_buttons,
        custom_classes: "organization-upgrade-banner",
        close_button: false,
    };

    banners.open(upgrade_banner, $upgrade_banner_containers);
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
