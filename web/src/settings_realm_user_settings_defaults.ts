import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_confirm_reset_user_configuration from "../templates/settings/confirm_reset_user_configuration.hbs";

import * as audible_notifications from "./audible_notifications.ts";
import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as information_density from "./information_density.ts";
import * as overlays from "./overlays.ts";
import * as people from "./people.ts";
import {
    realm_default_settings_schema,
    realm_user_settings_defaults,
} from "./realm_user_settings_defaults.ts";
import * as settings_components from "./settings_components.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_notifications from "./settings_notifications.ts";
import * as settings_org from "./settings_org.ts";
import * as settings_preferences from "./settings_preferences.ts";
import type {SettingsPanel} from "./settings_preferences.ts";
import * as settings_ui from "./settings_ui.ts";
import {current_user} from "./state_data.ts";
import type {HTMLSelectOneElement} from "./types.ts";
import * as ui_report from "./ui_report.ts";
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

        $(".organization-box [data-name='organization-level-user-defaults']")
            .find(".info-density-button")
            .prop("disabled", true);
        $(".organization-box [data-name='organization-level-user-defaults']")
            .find(".information-density-settings")
            .addClass("disabled-setting");

        $(".organization-box [data-name='organization-level-user-defaults']")
            .find(".reset-user-setting-to-default")
            .hide();
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

function get_realm_default_setting_value_for_reset(property: string): number | string | boolean {
    return realm_user_settings_defaults[
        z
            .keyof(
                z.omit(realm_default_settings_schema, {
                    available_notification_sounds: true,
                    emojiset_choices: true,
                }),
            )
            .parse(property)
    ];
}

function confirm_resetting_user_setting_to_default(
    property_list: string[],
    $status_element: JQuery,
): void {
    const modal_content_html = render_confirm_reset_user_configuration();

    function reset_user_configuration(): void {
        const active_human_user_ids = people.get_realm_active_human_user_ids();
        const deactivated_human_user_ids = people.get_non_active_human_ids();
        const target_users = {
            user_ids: [...active_human_user_ids, ...deactivated_human_user_ids],
            skip_if_already_edited: $("#users_to_reset_configuration").val() !== "everyone",
        };
        const data: Record<string, number | string | boolean> = {
            target_users: JSON.stringify(target_users),
        };
        for (const property of property_list) {
            data[property] = get_realm_default_setting_value_for_reset(property);
        }
        channel.patch({
            url: "/json/settings",
            data,
            success() {
                dialog_widget.close();
                ui_report.success($t_html({defaultMessage: "Saved"}), $status_element, 1500);
                settings_ui.display_checkmark($status_element);
            },
            error(xhr) {
                ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
            },
        });
    }

    dialog_widget.launch({
        modal_title_html: $t_html({defaultMessage: "Reset user configurations?"}),
        modal_content_html,
        id: "confirm-reset-user-configuration",
        on_click: reset_user_configuration,
        close_on_submit: false,
        loading_spinner: true,
        modal_submit_button_text: $t({defaultMessage: "Confirm"}),
        post_render() {
            $("#users_to_reset_configuration").val("everyone");
        },
    });
}

export function set_up(): void {
    assert(realm_default_settings_panel !== undefined);
    const $container = $(realm_default_settings_panel.container);
    const $notification_sound_dropdown = $container.find<HTMLSelectOneElement>(
        ".setting_notification_sound",
    );

    settings_preferences.set_up(realm_default_settings_panel);

    audible_notifications.update_notification_sound_source(
        "realm-default-notification-sound-audio",
        realm_default_settings_panel.settings_object,
    );

    $notification_sound_dropdown.on("change", () => {
        const sound = $notification_sound_dropdown.val()!.toLowerCase();
        audible_notifications.update_notification_sound_source(
            "realm-default-notification-sound-audio",
            {
                notification_sound: sound,
            },
        );
    });

    $container.find(".info-density-button").on("click", function (this: HTMLElement, e) {
        e.preventDefault();
        const changed_property = information_density.information_density_properties_schema.parse(
            $(this).closest(".button-group").attr("data-property"),
        );
        const new_value = information_density.get_new_value_for_information_density_settings(
            $(this),
            changed_property,
        );
        $(this).closest(".button-group").find(".current-value").val(new_value);
        let display_value = new_value.toString();
        if (changed_property === "web_line_height_percent") {
            display_value = information_density.get_string_display_value_for_line_height(new_value);
        }
        $(this).closest(".button-group").find(".display-value").text(display_value);
        information_density.enable_or_disable_control_buttons($container);
        const $subsection = $(this).closest(".settings-subsection-parent");
        settings_components.save_discard_default_realm_settings_widget_status_handler($subsection);
    });

    settings_notifications.set_up(realm_default_settings_panel);

    $("#realm_email_address_visibility").val(realm_user_settings_defaults.email_address_visibility);

    settings_org.register_save_discard_widget_handlers(
        $container,
        "/json/realm/user_settings_defaults",
        true,
    );

    $container.find(".reset-user-setting-to-default").on("click", function (this: HTMLElement) {
        let property_list = [];
        if ($(this).closest(".info-density-controls").length > 0) {
            // Information density settings do not follow the usual
            // convention of having "div.input-group" container for
            // each setting and thus they need to be handled here
            // in a different block.
            property_list = [
                $(this)
                    .closest(".info-density-controls")
                    .find(".button-group")
                    .attr("data-property")!,
            ];
        } else if ($(this).closest(".general_notifications").length > 0) {
            property_list = [
                ...settings_config.stream_notification_settings,
                ...settings_config.pm_mention_notification_settings,
                ...settings_config.followed_topic_notification_settings,
            ];
        } else {
            const $elem = $(this).closest(".input-group").find(".prop-element");
            property_list = [settings_components.extract_property_name($elem, true)];
        }
        const $status_element = $(this)
            .closest(".settings-subsection-parent")
            .find(".alert-notification");
        confirm_resetting_user_setting_to_default(property_list, $status_element);
    });

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
