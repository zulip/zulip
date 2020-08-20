"use strict";

const moment = require("moment-timezone");

const render_settings_tab = require("../templates/settings_tab.hbs");

const people = require("./people");
const settings_config = require("./settings_config");

$("body").ready(() => {
    $("#settings_overlay_container").on("click", (e) => {
        if (!overlays.is_modal_open()) {
            return;
        }
        if ($(e.target).closest(".modal").length > 0) {
            return;
        }
        e.preventDefault();
        e.stopPropagation();
        // Whenever opening a modal(over settings overlay) in an event handler
        // attached to a click event, make sure to stop the propagation of the
        // event to the parent container otherwise the modal will not open. This
        // is so because this event handler will get fired on any click in settings
        // overlay and subsequently close any open modal.
        overlays.close_active_modal();
    });
});

function setup_settings_label() {
    exports.settings_label = {
        // settings_notification
        enable_online_push_notifications: i18n.t(
            "Send mobile notifications even if I'm online (useful for testing)",
        ),
        pm_content_in_desktop_notifications: i18n.t(
            "Include content of private messages in desktop notifications",
        ),
        desktop_icon_count_display: i18n.t(
            "Unread count summary (appears in desktop sidebar and browser tab)",
        ),
        enable_digest_emails: i18n.t("Send digest emails when I'm away"),
        enable_login_emails: i18n.t("Send email notifications for new logins to my account"),
        message_content_in_email_notifications: i18n.t(
            "Include message content in missed message emails",
        ),
        realm_name_in_notifications: i18n.t(
            "Include organization name in subject of missed message emails",
        ),
        presence_enabled: i18n.t("Display my availability to other users when online"),

        // display settings
        dense_mode: i18n.t("Dense mode"),
        fluid_layout_width: i18n.t("Use full width on wide screens"),
        high_contrast_mode: i18n.t("High contrast mode"),
        left_side_userlist: i18n.t("Show user list on left sidebar in narrow windows"),
        starred_message_counts: i18n.t("Show counts for starred messages"),
        twenty_four_hour_time: i18n.t("Time format"),
        translate_emoticons: i18n.t(
            "Convert emoticons before sending (<code>:)</code> becomes 😃)",
        ),
    };
}

exports.build_page = function () {
    setup_settings_label();

    const rendered_settings_tab = render_settings_tab({
        full_name: people.my_full_name(),
        page_params,
        enable_sound_select:
            page_params.enable_sounds || page_params.enable_stream_audible_notifications,
        zuliprc: "zuliprc",
        botserverrc: "botserverrc",
        timezones: moment.tz.names(),
        can_create_new_bots: settings_bots.can_create_new_bots(),
        settings_label: exports.settings_label,
        demote_inactive_streams_values: settings_config.demote_inactive_streams_values,
        color_scheme_values: settings_config.color_scheme_values,
        twenty_four_hour_time_values: settings_config.twenty_four_hour_time_values,
        general_settings: settings_config.all_notifications().general_settings,
        notification_settings: settings_config.all_notifications().settings,
        desktop_icon_count_display_values: settings_notifications.desktop_icon_count_display_values,
        show_push_notifications_tooltip: settings_config.all_notifications()
            .show_push_notifications_tooltip,
        display_settings: settings_config.get_all_display_settings(),
        user_can_change_name: settings_account.user_can_change_name(),
        user_can_change_avatar: settings_account.user_can_change_avatar(),
    });

    $(".settings-box").html(rendered_settings_tab);
};

exports.launch = function (section) {
    exports.build_page();
    admin.build_page();
    settings_sections.reset_sections();

    overlays.open_settings();
    settings_panel_menu.normal_settings.activate_section_or_default(section);
    settings_toggle.highlight_toggle("settings");
};

exports.set_settings_header = function (key) {
    const header_text = $(`#settings_page .sidebar-list [data-section='${key}'] .text`).text();
    if (header_text) {
        $(".settings-header h1 .section").text(" / " + header_text);
    } else {
        blueslip.warn(
            "Error: the key '" +
                key +
                "' does not exist in the settings" +
                " sidebar list. Please add it.",
        );
    }
};

window.settings = exports;
