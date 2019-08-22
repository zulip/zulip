var render_settings_tab = require('../templates/settings_tab.hbs');

var settings = (function () {

var exports = {};

$("body").ready(function () {
    var $sidebar = $(".form-sidebar");
    var $targets = $sidebar.find("[data-target]");
    var $title = $sidebar.find(".title h1");
    var is_open = false;

    var close_sidebar = function () {
        $sidebar.removeClass("show");
        $sidebar.find("#edit_bot").empty();
        is_open = false;
    };

    exports.trigger_sidebar = function (target) {
        $targets.hide();
        var $target = $(".form-sidebar").find("[data-target='" + target + "']");

        $title.text($target.attr("data-title"));
        $target.show();

        $sidebar.addClass("show");
        is_open = true;
    };

    $(".form-sidebar .exit").click(function (e) {
        close_sidebar();
        e.stopPropagation();
    });

    $("body").click(function (e) {
        if (is_open && !$(e.target).within(".form-sidebar")) {
            close_sidebar();
        }
    });

    $("body").on("click", "[data-sidebar-form]", function (e) {
        exports.trigger_sidebar($(this).attr("data-sidebar-form"));
        e.stopPropagation();
    });

    $("body").on("click", "[data-sidebar-form-close]", close_sidebar);

    $("#settings_overlay_container").click(function (e) {
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
        // stream_notification_settings
        enable_stream_desktop_notifications: i18n.t("Visual desktop notifications"),
        enable_stream_audible_notifications: i18n.t("Audible desktop notifications"),
        enable_stream_push_notifications: i18n.t("Mobile notifications"),
        enable_stream_email_notifications: i18n.t("Email notifications"),

        // pm_mention_notification_settings
        enable_desktop_notifications: i18n.t("Visual desktop notifications"),
        enable_offline_email_notifications: i18n.t("Email notifications"),
        enable_offline_push_notifications: i18n.t("Mobile notifications"),
        enable_online_push_notifications: i18n.t("Send mobile notifications even if I'm online (useful for testing)"),
        enable_sounds: i18n.t("Audible desktop notifications"),
        pm_content_in_desktop_notifications: i18n.t("Include content of private messages in desktop notifications"),
        desktop_icon_count_display: i18n.t("Unread count summary (appears in desktop sidebar and browser tab)"),

        // other_notification_settings
        enable_digest_emails: i18n.t("Send digest emails when I'm away"),
        enable_login_emails: i18n.t("Send email notifications for new logins to my account"),
        message_content_in_email_notifications: i18n.t("Include message content in missed message emails"),
        realm_name_in_notifications: i18n.t("Include organization name in subject of missed message emails"),

        // display settings
        dense_mode: i18n.t("Dense mode"),
        fluid_layout_width: i18n.t("Use full width on wide screens"),
        high_contrast_mode: i18n.t("High contrast mode"),
        left_side_userlist: i18n.t("User list on left sidebar in narrow windows"),
        night_mode: i18n.t("Night mode"),
        starred_message_counts: i18n.t("Show counts for starred messages"),
        twenty_four_hour_time: i18n.t("24-hour time (17:00 instead of 5:00 PM)"),
        translate_emoticons: i18n.t("Convert emoticons before sending (<code>:)</code> becomes 😃)"),
    };
}

exports.build_page = function () {
    setup_settings_label();

    var rendered_settings_tab = render_settings_tab({
        full_name: people.my_full_name(),
        page_params: page_params,
        enable_sound_select: page_params.enable_sounds ||
            page_params.enable_stream_audible_notifications,
        zuliprc: 'zuliprc',
        botserverrc: 'botserverrc',
        timezones: moment.tz.names(),
        can_create_new_bots: settings_bots.can_create_new_bots(),
        settings_label: settings.settings_label,
        demote_inactive_streams_values: settings_display.demote_inactive_streams_values,
        notification_settings: settings_notifications.all_notifications.settings,
        desktop_icon_count_display_values: settings_notifications.desktop_icon_count_display_values,
        push_notification_tooltip:
            settings_notifications.all_notifications.push_notification_tooltip,
        display_settings: settings_display.all_display_settings,
        user_can_change_name: settings_account.user_can_change_name(),
    });

    $(".settings-box").html(rendered_settings_tab);
};

exports.launch = function (section) {
    exports.build_page();
    admin.build_page();
    settings_sections.reset_sections();

    overlays.open_settings();
    settings_panel_menu.normal_settings.activate_section(section);
    settings_toggle.highlight_toggle('settings');
};

exports.set_settings_header = function (key) {
    var header_text = $(`#settings_page .sidebar-list [data-section='${key}'] .text`).text();
    if (header_text) {
        $(".settings-header h1 .section").text(" / " + header_text);
    } else {
        blueslip.warn("Error: the key '" + key + "' does not exist in the settings" +
            " sidebar list. Please add it.");
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings;
}
window.settings = settings;
