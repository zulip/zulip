import $ from "jquery";

import * as audible_notifications from "./audible_notifications";
import {
    NON_COMPACT_MODE_FONT_SIZE_PX,
    NON_COMPACT_MODE_LINE_HEIGHT_PERCENT,
} from "./information_density";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults";
import * as settings_notifications from "./settings_notifications";
import * as settings_org from "./settings_org";
import * as settings_preferences from "./settings_preferences";
import {current_user} from "./state_data";

export const realm_default_settings_panel = {};

export function maybe_disable_widgets() {
    if (!current_user.is_admin) {
        $(".organization-box [data-name='organization-level-user-defaults']")
            .find("input, select")
            .prop("disabled", true);

        $(".organization-box [data-name='organization-level-user-defaults']")
            .find("input[type='checkbox']:disabled")
            .closest(".input-group")
            .addClass("control-label-disabled");

        $(".organization-box [data-name='organization-level-user-defaults']")
            .find(".play_notification_sound")
            .addClass("control-label-disabled");
    }
}

export function update_page(property) {
    if (!overlays.settings_open()) {
        return;
    }

    const $element = $(`#realm_${CSS.escape(property)}`);
    if ($element.length) {
        const $subsection = $element.closest(".settings-subsection-parent");
        if ($subsection.find(".save-button-controls").hasClass("hide")) {
            settings_org.discard_realm_default_property_element_changes($element[0]);
        } else {
            settings_org.discard_realm_default_settings_subsection_changes($subsection);
        }
    }
}

export function set_up() {
    const $container = $(realm_default_settings_panel.container);
    const $notification_sound_elem = $("audio#realm-default-notification-sound-audio");
    const $notification_sound_dropdown = $container.find(".setting_notification_sound");

    settings_preferences.set_up(realm_default_settings_panel);

    audible_notifications.update_notification_sound_source(
        $notification_sound_elem,
        realm_default_settings_panel.settings_object,
    );

    $notification_sound_dropdown.on("change", () => {
        const sound = $notification_sound_dropdown.val().toLowerCase();
        audible_notifications.update_notification_sound_source($notification_sound_elem, {
            notification_sound: sound,
        });
    });

    if (!page_params.development_environment) {
        $("#realm_dense_mode").on("change", (e) => {
            const val = $(e.target).prop("checked");
            if (val) {
                $container.find(".information-density-settings").hide();
                return;
            }

            if (
                !realm_user_settings_defaults.dense_mode &&
                (realm_user_settings_defaults.web_font_size_px !== NON_COMPACT_MODE_FONT_SIZE_PX ||
                    realm_user_settings_defaults.web_line_height_percent !==
                        NON_COMPACT_MODE_LINE_HEIGHT_PERCENT)
            ) {
                $container.find(".information-density-settings").show();
            }
        });
    }

    settings_notifications.set_up(realm_default_settings_panel);

    $("#realm_email_address_visibility").val(realm_user_settings_defaults.email_address_visibility);

    settings_org.register_save_discard_widget_handlers(
        $container,
        "/json/realm/user_settings_defaults",
        true,
    );

    maybe_disable_widgets();
}

export function initialize() {
    realm_default_settings_panel.container = "#realm-user-default-settings";
    realm_default_settings_panel.settings_object = realm_user_settings_defaults;
    realm_default_settings_panel.notification_sound_elem =
        "audio#realm-default-notification-sound-audio";
    realm_default_settings_panel.for_realm_settings = true;
}
