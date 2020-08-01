"use strict";

const render_stream_specific_notification_row = require("../templates/settings/stream_specific_notification_row.hbs");

const settings_config = require("./settings_config");

exports.get_notifications_table_row_data = function (notify_settings) {
    return settings_config.general_notifications_table_labels.realm.map((column, index) => {
        const setting_name = notify_settings[index];
        if (setting_name === undefined) {
            return {
                setting_name: "",
                is_disabled: true,
                is_checked: false,
            };
        }
        const checkbox = {
            setting_name,
            is_disabled: false,
        };
        if (column === "mobile") {
            checkbox.is_disabled = !page_params.realm_push_notifications_enabled;
        }
        checkbox.is_checked = page_params[setting_name];
        return checkbox;
    });
};

exports.desktop_icon_count_display_values = {
    messages: {
        code: 1,
        description: i18n.t("All unreads"),
    },
    notifiable: {
        code: 2,
        description: i18n.t("Private messages and mentions"),
    },
    none: {
        code: 3,
        description: i18n.t("None"),
    },
};

function rerender_ui() {
    const unmatched_streams_table = $("#stream-specific-notify-table");
    if (unmatched_streams_table.length === 0) {
        // If we haven't rendered "notification settings" yet, do nothing.
        return;
    }

    const unmatched_streams = stream_data.get_unmatched_streams_for_notification_settings();

    unmatched_streams_table.find(".stream-row").remove();

    for (const stream of unmatched_streams) {
        unmatched_streams_table.append(
            render_stream_specific_notification_row({
                stream,
                stream_specific_notification_settings:
                    settings_config.stream_specific_notification_settings,
                is_disabled: settings_config.all_notifications().show_push_notifications_tooltip,
            }),
        );
    }

    if (unmatched_streams.length === 0) {
        unmatched_streams_table.css("display", "none");
    } else {
        unmatched_streams_table.css("display", "table-row-group");
    }
}

function change_notification_setting(setting, setting_data, status_element) {
    const data = {};
    data[setting] = JSON.stringify(setting_data);
    settings_ui.do_settings_change(
        channel.patch,
        "/json/settings/notifications",
        data,
        status_element,
    );
}

function update_desktop_icon_count_display() {
    $("#desktop_icon_count_display").val(page_params.desktop_icon_count_display);
    const count = unread.get_notifiable_count();
    notifications.update_title_count(count);
}

exports.set_enable_digest_emails_visibility = function () {
    if (page_params.realm_digest_emails_enabled) {
        $("#enable_digest_emails_label").parent().show();
    } else {
        $("#enable_digest_emails_label").parent().hide();
    }
};

exports.set_up = function () {
    $("#notification-settings").on("change", "input, select", function (e) {
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
        );
    });

    update_desktop_icon_count_display();

    $("#send_test_notification").on("click", () => {
        notifications.send_test_notification(
            i18n.t("This is what a Zulip notification looks like."),
        );
    });

    $("#play_notification_sound").on("click", () => {
        $("#notifications-area").find("audio")[0].play();
    });

    const notification_sound_dropdown = $("#notification_sound");
    notification_sound_dropdown.val(page_params.notification_sound);

    $("#enable_sounds, #enable_stream_audible_notifications").on("change", () => {
        if (
            $("#enable_stream_audible_notifications").prop("checked") ||
            $("#enable_sounds").prop("checked")
        ) {
            notification_sound_dropdown.prop("disabled", false);
            notification_sound_dropdown.parent().removeClass("control-label-disabled");
        } else {
            notification_sound_dropdown.prop("disabled", true);
            notification_sound_dropdown.parent().addClass("control-label-disabled");
        }
    });
    exports.set_enable_digest_emails_visibility();
    rerender_ui();
};

exports.update_page = function () {
    for (const setting of settings_config.all_notification_settings) {
        if (
            setting === "enable_offline_push_notifications" &&
            !page_params.realm_push_notifications_enabled
        ) {
            // If push notifications are disabled at the realm level,
            // we should just leave the checkbox always off.
            continue;
        } else if (setting === "desktop_icon_count_display") {
            update_desktop_icon_count_display();
            continue;
        }

        $("#" + setting).prop("checked", page_params[setting]);
    }
    rerender_ui();
};

window.settings_notifications = exports;
