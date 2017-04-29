var settings_notifications = (function () {

var exports = {};

exports.set_up = function () {
    $("#notify-settings-status").hide();

    if (!page_params.realm_show_digest_email) {
        $("#other_notifications").hide();
    }

    function update_notification_settings_success(resp, statusText, xhr) {
        var result = JSON.parse(xhr.responseText);
        var notify_settings_status = $('#notify-settings-status').expectOne();

        // Stream notification settings.

        if (result.enable_stream_desktop_notifications !== undefined) {
            page_params.enable_stream_desktop_notifications =
                result.enable_stream_desktop_notifications;
        }
        if (result.enable_stream_sounds !== undefined) {
            page_params.enable_stream_sounds = result.enable_stream_sounds;
        }

        // PM and @-mention notification settings.

        if (result.enable_desktop_notifications !== undefined) {
            page_params.enable_desktop_notifications = result.enable_desktop_notifications;
        }
        if (result.enable_sounds !== undefined) {
            page_params.enable_sounds = result.enable_sounds;
        }

        if (result.enable_offline_email_notifications !== undefined) {
            page_params.enable_offline_email_notifications =
                result.enable_offline_email_notifications;
        }

        if (result.enable_offline_push_notifications !== undefined) {
            page_params.enable_offline_push_notifications =
                result.enable_offline_push_notifications;
        }

        if (result.enable_online_push_notifications !== undefined) {
            page_params.enable_online_push_notifications = result.enable_online_push_notifications;
        }

        if (result.pm_content_in_desktop_notifications !== undefined) {
            page_params.pm_content_in_desktop_notifications
                = result.pm_content_in_desktop_notifications;
        }
        // Other notification settings.

        if (result.enable_digest_emails !== undefined) {
            page_params.enable_digest_emails = result.enable_digest_emails;
        }

        ui_report.success(i18n.t("Updated notification settings!"), notify_settings_status);
    }

    function update_notification_settings_error(xhr) {
        ui_report.error(i18n.t("Error changing settings"), xhr, $('#notify-settings-status').expectOne());
    }

    function post_notify_settings_changes(notification_changes, success_func,
                                          error_func) {
        return channel.patch({
            url: "/json/settings/notifications",
            data: notification_changes,
            success: success_func,
            error: error_func,
        });
    }

    $("#change_notification_settings").on("click", function (e) {
        e.preventDefault();

        var updated_settings = {};
        _.each(["enable_stream_desktop_notifications", "enable_stream_sounds",
                "enable_desktop_notifications", "pm_content_in_desktop_notifications", "enable_sounds",
                "enable_offline_email_notifications",
                "enable_offline_push_notifications", "enable_online_push_notifications",
                "enable_digest_emails"],
               function (setting) {
                   updated_settings[setting] = $("#" + setting).is(":checked");
               });
        post_notify_settings_changes(updated_settings,
                                     update_notification_settings_success,
                                     update_notification_settings_error);
    });

    function update_global_stream_setting(notification_type, new_setting) {
        var data = {};
        data[notification_type] = new_setting;
        channel.patch({
            url: "/json/settings/notifications",
            data: data,
            success: update_notification_settings_success,
            error: update_notification_settings_error,
        });
    }

    function update_desktop_notification_setting(new_setting) {
        update_global_stream_setting("enable_stream_desktop_notifications", new_setting);
        stream_edit.set_all_stream_desktop_notifications_to(new_setting);
    }

    function update_audible_notification_setting(new_setting) {
        update_global_stream_setting("enable_stream_sounds", new_setting);
        stream_edit.set_all_stream_audible_notifications_to(new_setting);
    }

    function maybe_bulk_update_stream_notification_setting(notification_checkbox,
                                                           propagate_setting_function) {
        var html = templates.render("propagate_notification_change");
        // TODO: This seems broken!!!
        var control_group = notification_checkbox.closest(".control-group");
        var checkbox_status = notification_checkbox.is(":checked");
        control_group.find(".propagate_stream_notifications_change").html(html);
        control_group.find(".yes_propagate_notifications").on("click", function () {
            propagate_setting_function(checkbox_status);
            control_group.find(".propagate_stream_notifications_change").empty();
        });
        control_group.find(".no_propagate_notifications").on("click", function () {
            control_group.find(".propagate_stream_notifications_change").empty();
        });
    }

    $("#enable_stream_desktop_notifications").on("click", function () {
        var notification_checkbox = $("#enable_stream_desktop_notifications");
        maybe_bulk_update_stream_notification_setting(notification_checkbox,
                                                      update_desktop_notification_setting);
    });

    $("#enable_stream_sounds").on("click", function () {
        var notification_checkbox = $("#enable_stream_sounds");
        maybe_bulk_update_stream_notification_setting(notification_checkbox,
                                                      update_audible_notification_setting);
    });

};

function _update_page() {
    $("#enable_stream_desktop_notifications").prop('checked', page_params.enable_stream_desktop_notifications);
    $("#enable_stream_sounds").prop('checked', page_params.enable_stream_sounds);
    $("#enable_desktop_notifications").prop('checked', page_params.enable_desktop_notifications);
    $("#enable_sounds").prop('checked', page_params.enable_sounds);
    $("#enable_offline_email_notifications").prop('checked', page_params.enable_offline_email_notifications);
    $("#enable_offline_push_notifications").prop('checked', page_params.enable_offline_push_notifications);
    $("#enable_online_push_notifications").prop('checked', page_params.enable_online_push_notifications);
    $("#pm_content_in_desktop_notifications").prop('checked', page_params.pm_content_in_desktop_notifications);
    $("#enable_digest_emails").prop('checked', page_params.enable_digest_emails);
}

exports.update_page = function () {
    i18n.ensure_i18n(_update_page);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_notifications;
}
