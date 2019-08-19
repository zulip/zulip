var settings_notifications = (function () {

var exports = {};

var stream_notification_settings = [
    "enable_stream_desktop_notifications",
    "enable_stream_audible_notifications",
    "enable_stream_push_notifications",
    "enable_stream_email_notifications",
];

var pm_mention_notification_settings = [
    "enable_desktop_notifications",
    "enable_sounds",
    "enable_offline_push_notifications",
    "enable_offline_email_notifications",
];

var desktop_notification_settings = [
    "pm_content_in_desktop_notifications",
];

var mobile_notification_settings = [
    "enable_online_push_notifications",
];

var email_notification_settings = [
    "enable_digest_emails",
    "enable_login_emails",
    "message_content_in_email_notifications",
    "realm_name_in_notifications",
];

var other_notification_settings = desktop_notification_settings.concat(
    ["desktop_icon_count_display"],
    mobile_notification_settings,
    email_notification_settings,
    ["notification_sound"]
);

var notification_settings_status = [
    {status_label: "pm-mention-notify-settings-status", settings: pm_mention_notification_settings},
    {status_label: "other-notify-settings-status", settings: other_notification_settings},
    {status_label: "stream-notify-settings-status", settings: stream_notification_settings},
];

exports.all_notification_settings_labels = other_notification_settings.concat(
    pm_mention_notification_settings,
    stream_notification_settings
);

exports.all_notifications = {
    settings: {
        stream_notification_settings: stream_notification_settings,
        pm_mention_notification_settings: pm_mention_notification_settings,
        desktop_notification_settings: desktop_notification_settings,
        mobile_notification_settings: mobile_notification_settings,
        email_notification_settings: email_notification_settings,
    },
    push_notification_tooltip: {
        enable_stream_push_notifications: true,
        enable_offline_push_notifications: true,
        enable_online_push_notifications: true,
    },
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

function change_notification_setting(setting, setting_data, status_element) {
    var data = {};
    data[setting] = JSON.stringify(setting_data);
    settings_ui.do_settings_change(channel.patch, '/json/settings/notifications', data, status_element);
}

function update_desktop_icon_count_display() {
    $("#desktop_icon_count_display").val(page_params.desktop_icon_count_display);
    var count = unread.get_notifiable_count();
    notifications.update_title_count(count);
}

exports.set_enable_digest_emails_visibility = function () {
    if (page_params.realm_digest_emails_enabled) {
        $('#enable_digest_emails_label').parent().show();
    } else {
        $('#enable_digest_emails_label').parent().hide();
    }
};

exports.set_up = function () {
    _.each(notification_settings_status, function (setting) {
        _.each(setting.settings, function (sub_setting) {
            $("#" + sub_setting).change(function () {
                var value;

                // `notification_sound` and `desktop_icon_count_display` are not booleans.
                if (sub_setting === "notification_sound") {
                    value = $(this).val();
                } else if (sub_setting === "desktop_icon_count_display") {
                    value = parseInt($(this).val(), 10);
                } else {
                    value = $(this).prop('checked');
                }
                change_notification_setting(sub_setting, value,
                                            "#" + setting.status_label);
            });
        });
    });

    update_desktop_icon_count_display();

    $("#play_notification_sound").click(function () {
        $("#notifications-area").find("audio")[0].play();
    });

    var notification_sound_dropdown = $("#notification_sound");
    notification_sound_dropdown.val(page_params.notification_sound);

    $("#enable_sounds, #enable_stream_audible_notifications").change(function () {
        if ($("#enable_stream_audible_notifications").prop("checked") || $("#enable_sounds").prop("checked")) {
            notification_sound_dropdown.prop("disabled", false);
            notification_sound_dropdown.parent().removeClass("control-label-disabled");
        } else {
            notification_sound_dropdown.prop("disabled", true);
            notification_sound_dropdown.parent().addClass("control-label-disabled");
        }
    });
    exports.set_enable_digest_emails_visibility();
};

exports.update_page = function () {
    _.each(exports.all_notification_settings_labels, function (setting) {
        if (setting === 'enable_offline_push_notifications'
            && !page_params.realm_push_notifications_enabled) {
            // If push notifications are disabled at the realm level,
            // we should just leave the checkbox always off.
            return;
        } else if (setting === 'desktop_icon_count_display') {
            update_desktop_icon_count_display();
            return;
        }

        $("#" + setting).prop('checked', page_params[setting]);
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_notifications;
}
window.settings_notifications = settings_notifications;
