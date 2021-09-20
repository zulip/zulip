import $ from "jquery";

import render_stream_specific_notification_row from "../templates/settings/stream_specific_notification_row.hbs";

import * as channel from "./channel";
import {$t} from "./i18n";
import * as notifications from "./notifications";
import {page_params} from "./page_params";
import * as settings_config from "./settings_config";
import * as settings_org from "./settings_org";
import * as settings_ui from "./settings_ui";
import * as stream_edit from "./stream_edit";
import * as stream_settings_data from "./stream_settings_data";
import * as unread_ui from "./unread_ui";
import {user_settings} from "./user_settings";

export const user_settings_panel = {};

function rerender_ui() {
    const unmatched_streams_table = $("#stream-specific-notify-table");
    if (unmatched_streams_table.length === 0) {
        // If we haven't rendered "notification settings" yet, do nothing.
        return;
    }

    const unmatched_streams =
        stream_settings_data.get_unmatched_streams_for_notification_settings();

    unmatched_streams_table.find(".stream-row").remove();

    for (const stream of unmatched_streams) {
        unmatched_streams_table.append(
            render_stream_specific_notification_row({
                stream,
                stream_specific_notification_settings:
                    settings_config.stream_specific_notification_settings,
                is_disabled:
                    settings_config.all_notifications(user_settings)
                        .show_push_notifications_tooltip,
            }),
        );
    }

    if (unmatched_streams.length === 0) {
        unmatched_streams_table.css("display", "none");
    } else {
        unmatched_streams_table.css("display", "table-row-group");
    }
}

function change_notification_setting(setting, value, status_element, url) {
    const data = {};
    data[setting] = value;
    settings_ui.do_settings_change(channel.patch, url, data, status_element);
}

function update_desktop_icon_count_display(settings_panel) {
    const container = $(settings_panel.container);
    const settings_object = settings_panel.settings_object;
    container
        .find(".setting_desktop_icon_count_display")
        .val(settings_object.desktop_icon_count_display);
    if (!settings_panel.for_realm_settings) {
        unread_ui.update_unread_counts();
    }
}

export function set_enable_digest_emails_visibility(container) {
    if (page_params.realm_digest_emails_enabled) {
        container.find(".enable_digest_emails_label").parent().show();
    } else {
        container.find(".enable_digest_emails_label").parent().hide();
    }
}

export function set_enable_marketing_emails_visibility() {
    const container = $("#user-notification-settings");
    if (page_params.corporate_enabled) {
        container.find(".enable_marketing_emails_label").parent().show();
    } else {
        container.find(".enable_marketing_emails_label").parent().hide();
    }
}

export function set_up(settings_panel) {
    const container = $(settings_panel.container);
    const settings_object = settings_panel.settings_object;
    const patch_url = settings_panel.patch_url;
    const notification_sound_elem = $(settings_panel.notification_sound_elem);
    const for_realm_settings = settings_panel.for_realm_settings;

    container.find(".notification-settings-form").on("change", "input, select", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const input_elem = $(e.currentTarget);
        if (input_elem.parents("#stream-specific-notify-table").length) {
            stream_edit.stream_setting_changed(e, true);
            return;
        }
        const setting_name = input_elem.attr("name");
        change_notification_setting(
            setting_name,
            settings_org.get_input_element_value(this),
            input_elem.closest(".subsection-parent").find(".alert-notification"),
            patch_url,
        );
    });

    update_desktop_icon_count_display(settings_panel);

    if (!for_realm_settings) {
        container.find(".send_test_notification").on("click", () => {
            notifications.send_test_notification(
                $t({defaultMessage: "This is what a Zulip notification looks like."}),
            );
        });
    }

    container.find(".play_notification_sound").on("click", () => {
        if (settings_object.notification_sound !== "none") {
            notification_sound_elem[0].play();
        }
    });

    const notification_sound_dropdown = container.find(".setting_notification_sound");
    notification_sound_dropdown.val(settings_object.notification_sound);

    container.find(".enable_sounds, .enable_stream_audible_notifications").on("change", () => {
        if (
            container.find(".enable_stream_audible_notifications").prop("checked") ||
            container.find(".enable_sounds").prop("checked")
        ) {
            notification_sound_dropdown.prop("disabled", false);
            notification_sound_dropdown.parent().removeClass("control-label-disabled");
        } else {
            notification_sound_dropdown.prop("disabled", true);
            notification_sound_dropdown.parent().addClass("control-label-disabled");
        }
    });

    const email_notifications_batching_period_dropdown = container.find(
        ".setting_email_notifications_batching_period_seconds",
    );
    email_notifications_batching_period_dropdown.val(
        settings_object.email_notifications_batching_period_seconds,
    );

    set_enable_digest_emails_visibility(container);
    if (!for_realm_settings) {
        set_enable_marketing_emails_visibility();
        rerender_ui();
    }
}

export function update_page(settings_panel) {
    const container = $(settings_panel.container);
    const settings_object = settings_panel.settings_object;
    for (const setting of settings_config.all_notification_settings) {
        if (
            setting === "enable_offline_push_notifications" &&
            !page_params.realm_push_notifications_enabled
        ) {
            // If push notifications are disabled at the realm level,
            // we should just leave the checkbox always off.
            continue;
        } else if (setting === "desktop_icon_count_display") {
            update_desktop_icon_count_display(settings_panel);
            continue;
        } else if (
            setting === "notification_sound" ||
            setting === "email_notifications_batching_period_seconds"
        ) {
            container.find(`.setting_${CSS.escape(setting)}`).val(settings_object[setting]);
            continue;
        }

        container.find(`.${CSS.escape(setting)}`).prop("checked", settings_object[setting]);
    }
    rerender_ui();
}

export function initialize() {
    user_settings_panel.container = "#user-notification-settings";
    user_settings_panel.settings_object = user_settings;
    user_settings_panel.patch_url = "/json/settings";
    user_settings_panel.notification_sound_elem = "#user-notification-sound-audio";
    user_settings_panel.for_realm_settings = false;
}
