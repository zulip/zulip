import $ from "jquery";
import assert from "minimalistic-assert";

import * as audible_notifications from "./audible_notifications.ts";
import * as overlays from "./overlays.ts";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults.ts";
import * as settings_notifications from "./settings_notifications.ts";
import * as settings_org from "./settings_org.ts";
import * as settings_preferences from "./settings_preferences.ts";
import type {SettingsPanel} from "./settings_preferences.ts";
import {current_user} from "./state_data.ts";
import type {HTMLSelectOneElement} from "./types.ts";
import * as util from "./util.ts";

export let realm_default_settings_panel: SettingsPanel | undefined;

export function maybe_disable_widgets(): void {
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

export function update_page(property: string): void {
    if (!overlays.settings_open()) {
        return;
    }

    const $element = $(`#realm_${CSS.escape(property)}`);
    if ($element.length > 0) {
        const $subsection = $element.closest(".settings-subsection-parent");
        if ($subsection.find(".save-button-controls").hasClass("hide")) {
            settings_org.discard_realm_default_property_element_changes(util.the($element));
        } else {
            settings_org.discard_realm_default_settings_subsection_changes($subsection);
        }
    }
}

export function set_up(): void {
    assert(realm_default_settings_panel !== undefined);
    const $container = $(realm_default_settings_panel.container);
    const $notification_sound_elem = $<HTMLAudioElement>(
        "audio#realm-default-notification-sound-audio",
    );
    const $notification_sound_dropdown = $container.find<HTMLSelectOneElement>(
        ".setting_notification_sound",
    );

    settings_preferences.set_up(realm_default_settings_panel);

    audible_notifications.update_notification_sound_source(
        $notification_sound_elem,
        realm_default_settings_panel.settings_object,
    );

    $notification_sound_dropdown.on("change", () => {
        const sound = $notification_sound_dropdown.val()!.toLowerCase();
        audible_notifications.update_notification_sound_source($notification_sound_elem, {
            notification_sound: sound,
        });
    });

    settings_notifications.set_up(realm_default_settings_panel);

    $("#realm_email_address_visibility").val(realm_user_settings_defaults.email_address_visibility);

    settings_org.register_save_discard_widget_handlers(
        $container,
        "/json/realm/user_settings_defaults",
        true,
    );

    maybe_disable_widgets();
}

export function initialize(): void {
    realm_default_settings_panel = {
        container: "#realm-user-default-settings",
        settings_object: realm_user_settings_defaults,
        notification_sound_elem: "audio#realm-default-notification-sound-audio",
        for_realm_settings: true,
    };
}
