var settings_notifications = (function () {

var exports = {};

var stream_notification_settings = [
    {setting: "enable_stream_desktop_notifications", notifications:"desktop_notifications"},
    {setting: "enable_stream_push_notifications", notifications:"push_notifications"},
    {setting: "enable_stream_sounds", notifications:"audible_notifications"},
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
    "enable_digest_emails",
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
    if (!page_params.realm_show_digest_email) {
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
            change_notification_setting(setting, $(this).prop('checked'),
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

    $("#enable_desktop_notifications").change(function () {
        settings_ui.disable_sub_setting_onchange(this.checked, "pm_content_in_desktop_notifications", true);
    });

    $("#enable_offline_push_notifications").change(function () {
        settings_ui.disable_sub_setting_onchange(this.checked, "enable_online_push_notifications", true);
    });
};

function _update_page() {
    _.each(exports.notification_settings, function (setting) {
        $("#" + setting).prop('checked', page_params[setting]);
    });
}

exports.update_page = function () {
    i18n.ensure_i18n(_update_page);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_notifications;
}
