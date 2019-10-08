var settings = (function () {

var exports = {};
var header_map = {
    "your-account": i18n.t("Your account"),
    "display-settings": i18n.t("Display settings"),
    notifications: i18n.t("Notifications"),
    "your-bots": i18n.t("Your bots"),
    "alert-words": i18n.t("Alert words"),
    "uploaded-files": i18n.t("Uploaded files"),
    "muted-topics": i18n.t("Muted topics"),
    "organization-profile": i18n.t("Organization profile"),
    "organization-settings": i18n.t("Organization settings"),
    "organization-permissions": i18n.t("Organization permissions"),
    "emoji-settings": i18n.t("Emoji settings"),
    "auth-methods": i18n.t("Authorization methods"),
    "user-list-admin": i18n.t("Active users"),
    "deactivated-users-admin": i18n.t("Deactivated users"),
    "bot-list-admin": i18n.t("Bot list"),
    "default-streams-list": i18n.t("Default streams"),
    "filter-settings": i18n.t("Linkifiers"),
    "invites-list-admin": i18n.t("Invitations"),
    "user-groups-admin": i18n.t("User groups"),
    "profile-field-settings": i18n.t("Profile field settings"),
};

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
        enable_stream_sounds: i18n.t("Audible desktop notifications"),
        enable_stream_push_notifications: i18n.t("Mobile notifications"),
        enable_stream_email_notifications: i18n.t("Email notifications"),

        // pm_mention_notification_settings
        enable_desktop_notifications: i18n.t("Visual desktop notifications"),
        enable_offline_email_notifications: i18n.t("Email notifications when offline"),
        enable_offline_push_notifications: i18n.t("Mobile notifications when offline"),
        enable_online_push_notifications: i18n.t("Mobile notifications always (even when online)"),
        enable_sounds: i18n.t("Audible desktop notifications"),
        pm_content_in_desktop_notifications: i18n.t("Include content of private messages"),

        // other_notification_settings
        enable_digest_emails: i18n.t("Send digest emails when I'm away"),
        enable_login_emails: i18n.t("Send email notifications for new logins to my account"),
        message_content_in_email_notifications: i18n.t("Include message content in missed message emails"),
        realm_name_in_notifications: i18n.t("Include organization name in subject of missed message emails"),

        // display settings
        dense_mode: i18n.t("Dense mode"),
        high_contrast_mode: i18n.t("High contrast mode"),
        left_side_userlist: i18n.t("User list on left sidebar in narrow windows"),
        night_mode: i18n.t("Night mode"),
        starred_message_counts: i18n.t("Show counts for starred messages"),
        twenty_four_hour_time: i18n.t("24-hour time (17:00 instead of 5:00 PM)"),
        translate_emoticons: i18n.t("Convert emoticons before sending (<code>:)</code> becomes 😃)"),
    };
}

exports.build_page = function () {
    ui.set_up_scrollbar($("#settings_page .sidebar.left"));
    ui.set_up_scrollbar($("#settings_content"));

    setup_settings_label();

    var rendered_settings_tab = templates.render('settings_tab', {
        full_name: people.my_full_name(),
        page_params: page_params,
        enable_sound_select: page_params.enable_sounds || page_params.enable_stream_sounds,
        zuliprc: 'zuliprc',
        botserverrc: 'botserverrc',
        timezones: moment.tz.names(),
        can_create_new_bots: settings_bots.can_create_new_bots(),
        settings_label: settings.settings_label,
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
    if (header_map[key]) {
        $(".settings-header h1 .section").text(" / " + header_map[key]);
    } else {
        blueslip.warn("Error: the key '" + key + "' does not exist in the settings" +
            " header mapping file. Please add it.");
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings;
}
window.settings = settings;
