var settings_notifications = (function () {

var exports = {};

var notification_settings = [
    "enable_desktop_notifications",
    "enable_digest_emails",
    "enable_offline_email_notifications",
    "enable_offline_push_notifications",
    "enable_online_push_notifications",
    "enable_sounds",
    "enable_stream_desktop_notifications",
    "enable_stream_sounds",
    "pm_content_in_desktop_notifications",
];

exports.set_up = function () {
    var notify_settings_status = $("#notify-settings-status").expectOne();
    notify_settings_status.hide();

    if (!page_params.realm_show_digest_email) {
        $("#other_notifications").hide();
    }

    _.each(notification_settings, function (setting) {
         $("#" + setting).change(function () {
            var data = {};
            var setting_name = $('label[for=' + setting + ']').text().trim();
            var context = {setting_name: setting_name};
            data[setting] = JSON.stringify(this.checked);

            channel.patch({
                url: '/json/settings/notifications',
                data: data,
                success: function () {
                    if (data[setting] === 'true') {
                        ui_report.success(i18n.t("Enabled: __setting_name__",
                            context), notify_settings_status);
                    } else {
                        ui_report.success(i18n.t("Disabled: __setting_name__",
                            context), notify_settings_status);
                    }
                },
                error: function (xhr) {
                    ui_report.error(i18n.t('Error updating: __setting_name__',
                        context), xhr, notify_settings_status);
                },
            });
            if (setting === 'enable_stream_desktop_notifications') {
                stream_edit.set_notification_setting_for_all_streams('desktop_notifications', data[setting]);
            } else if (setting === 'enable_stream_sounds') {
                stream_edit.set_notification_setting_for_all_streams('audible_notifications', data[setting]);
            }
        });
    });
};

function _update_page() {
    _.each(notification_settings, function (setting) {
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
