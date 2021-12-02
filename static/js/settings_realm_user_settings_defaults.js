import $ from "jquery";

import * as overlays from "./overlays";
import {page_params} from "./page_params";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults";
import * as settings_display from "./settings_display";
import * as settings_notifications from "./settings_notifications";
import * as settings_org from "./settings_org";

export const realm_default_settings_panel = {};

export function maybe_disable_widgets() {
    if (!page_params.is_admin) {
        $(".organization-box [data-name='organization-level-user-defaults']")
            .find("input, select")
            .prop("disabled", true);

        $(".organization-box [data-name='organization-level-user-defaults']")
            .find(".play_notification_sound")
            .addClass("control-label-disabled");
    }
}

export function update_page(property) {
    if (!overlays.settings_open()) {
        return;
    }
    const container = $(realm_default_settings_panel.container);
    let value = realm_user_settings_defaults[property];

    // settings_org.set_input_element_value doesn't support radio
    // button widgets like this one.
    if (property === "emojiset") {
        container.find(`input[value=${CSS.escape(value)}]`).prop("checked", true);
        return;
    }

    if (property === "email_notifications_batching_period_seconds") {
        settings_notifications.set_notification_batching_ui(container, value);
        return;
    }

    // The twenty_four_hour_time setting is represented as a boolean
    // in the API, but a dropdown with "true"/"false" as strings in
    // the UI, so we need to convert its format here.
    if (property === "twenty_four_hour_time") {
        value = value.toString();
    }

    const input_elem = container.find(`[name=${CSS.escape(property)}]`);
    settings_org.set_input_element_value(input_elem, value);
}

export function set_up() {
    const container = $(realm_default_settings_panel.container);
    settings_display.set_up(realm_default_settings_panel);
    settings_notifications.set_up(realm_default_settings_panel);

    settings_org.register_save_discard_widget_handlers(
        container,
        "/json/realm/user_settings_defaults",
        true,
    );

    maybe_disable_widgets();
}

export function initialize() {
    realm_default_settings_panel.container = "#realm-user-default-settings";
    realm_default_settings_panel.settings_object = realm_user_settings_defaults;
    realm_default_settings_panel.notification_sound_elem =
        "#realm-default-notification-sound-audio";
    realm_default_settings_panel.for_realm_settings = true;
}
