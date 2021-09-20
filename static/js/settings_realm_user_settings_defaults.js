import $ from "jquery";

import * as channel from "./channel";
import {page_params} from "./page_params";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults";
import * as settings_display from "./settings_display";
import * as settings_notifications from "./settings_notifications";
import * as settings_ui from "./settings_ui";

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
export function set_up() {
    const container = $(realm_default_settings_panel.container);
    settings_display.set_up(realm_default_settings_panel);
    settings_notifications.set_up(realm_default_settings_panel);

    container.find(".presence_enabled").on("change", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const data = {presence_enabled: container.find(".presence_enabled").prop("checked")};
        settings_ui.do_settings_change(
            channel.patch,
            "/json/realm/user_settings_defaults",
            data,
            container.find(".privacy-setting-status").expectOne(),
        );
    });

    container.find(".enter_sends").on("change", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const data = {enter_sends: container.find(".enter_sends").prop("checked")};
        settings_ui.do_settings_change(
            channel.patch,
            "/json/realm/user_settings_defaults",
            data,
            container.find(".other-setting-status").expectOne(),
        );
    });

    maybe_disable_widgets();
}

export function initialize() {
    realm_default_settings_panel.container = "#realm-user-default-settings";
    realm_default_settings_panel.settings_object = realm_user_settings_defaults;
    realm_default_settings_panel.patch_url = "/json/realm/user_settings_defaults";
    realm_default_settings_panel.notification_sound_elem =
        "#realm-default-notification-sound-audio";
    realm_default_settings_panel.for_realm_settings = true;
}
