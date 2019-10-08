var settings_notifications = (function () {

var exports = {};

var stream_notification_settings = [
    {setting: "enable_stream_desktop_notifications", notifications: "desktop_notifications"},
    {setting: "enable_stream_push_notifications", notifications: "push_notifications"},
    {setting: "enable_stream_sounds", notifications: "audible_notifications"},
    {setting: "enable_stream_email_notifications", notifications: "email_notifications"},
];

var pm_mention_notification_settings = [
    "enable_desktop_notifications",
    "enable_offline_email_notifications",
    "enable_offline_push_notifications",
    "enable_online_push_notifications",
    "enable_sounds",
    "pm_content_in_desktop_notifications",
];

var other_notification_settings = [
    "notification_sound",
    "enable_digest_emails",
    "enable_login_emails",
    "realm_name_in_notifications",
    "message_content_in_email_notifications",
];

exports.notification_settings = other_notification_settings.concat(
    pm_mention_notification_settings,
    _.pluck(stream_notification_settings, 'setting')
);

function maybe_bulk_update_stream_notification_setting(notification_checkbox,
                                                       propagate_setting_function) {
    var html = templates.render("propagate_notification_change");
    // TODO: This seems broken!!!
    var group = notification_checkbox.closest(".input-group");
    var checkbox_status = notification_checkbox.prop('checked');
    group.find(".propagate_stream_notifications_change").html(html);
    group.find(".yes_propagate_notifications").on("click", function () {
        propagate_setting_function(checkbox_status);
        group.find(".propagate_stream_notifications_change").empty();
    });
    group.find(".no_propagate_notifications").on("click", function () {
        group.find(".propagate_stream_notifications_change").empty();
    });
}

function change_notification_setting(setting, setting_data, status_element) {
    var data = {};
    data[setting] = JSON.stringify(setting_data);
    settings_ui.do_settings_change(channel.patch, '/json/settings/notifications', data, status_element);
}

exports.set_up = function () {
    if (!page_params.realm_digest_emails_enabled) {
        $("#digest_container").hide();
    }

    _.each(pm_mention_notification_settings, function (setting) {
        $("#" + setting).change(function () {
            change_notification_setting(setting, $(this).prop('checked'),
                                        "#pm-mention-notify-settings-status");
        });
    });

    _.each(other_notification_settings, function (setting) {
        $("#" + setting).change(function () {
            var value;

            if (setting === "notification_sound") {
                // `notification_sound` is not a boolean.
                value = $(this).val();
            } else {
                value = $(this).prop('checked');
            }

            change_notification_setting(setting, value,
                                        "#other-notify-settings-status");
        });
    });

    _.each(stream_notification_settings, function (stream_setting) {
        var setting = stream_setting.setting;
        $("#" + setting).change(function () {
            var setting_data = $(this).prop('checked');
            change_notification_setting(setting, setting_data, "#stream-notify-settings-status");
            maybe_bulk_update_stream_notification_setting($('#' + setting), function () {
                stream_edit.set_notification_setting_for_all_streams(
                    stream_setting.notifications, setting_data);
            });
        });
    });

    $("#play_notification_sound").click(function () {
        $("#notifications-area").find("audio")[0].play();
    });

    var notification_sound_dropdown = $("#notification_sound");
    notification_sound_dropdown.val(page_params.notification_sound);

    $("#enable_sounds, #enable_stream_sounds").change(function () {
        if ($("#enable_stream_sounds").prop("checked") || $("#enable_sounds").prop("checked")) {
            notification_sound_dropdown.prop("disabled", false);
            notification_sound_dropdown.parent().removeClass("control-label-disabled");
        } else {
            notification_sound_dropdown.prop("disabled", true);
            notification_sound_dropdown.parent().addClass("control-label-disabled");
        }
    });

    $("#enable_desktop_notifications").change(function () {
        settings_ui.disable_sub_setting_onchange(this.checked, "pm_content_in_desktop_notifications", true);
    });

    $("#enable_offline_push_notifications").change(function () {
        settings_ui.disable_sub_setting_onchange(this.checked, "enable_online_push_notifications", true);
    });
};

exports.update_page = function () {
    _.each(exports.notification_settings, function (setting) {
        $("#" + setting).prop('checked', page_params[setting]);
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_notifications;
}
window.settings_notifications = settings_notifications;
