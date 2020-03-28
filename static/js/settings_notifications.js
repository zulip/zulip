const general_notifications_table_columns = [
    /* An array of notification settings of any category like
    * `stream_notification_settings` which makes a single row of
    * "Notification triggers" table should follow this order
    */
    "visual", "audio", "mobile", "email", "all_mentions",
];

exports.stream_notification_settings = [
    "enable_stream_desktop_notifications",
    "enable_stream_audible_notifications",
    "enable_stream_push_notifications",
    "enable_stream_email_notifications",
    "wildcard_mentions_notify",
];

const pm_mention_notification_settings = [
    "enable_desktop_notifications",
    "enable_sounds",
    "enable_offline_push_notifications",
    "enable_offline_email_notifications",
];

const desktop_notification_settings = [
    "pm_content_in_desktop_notifications",
];

const mobile_notification_settings = [
    "enable_online_push_notifications",
];

const email_notification_settings = [
    "enable_digest_emails",
    "enable_login_emails",
    "message_content_in_email_notifications",
    "realm_name_in_notifications",
];

const other_notification_settings = desktop_notification_settings.concat(
    ["desktop_icon_count_display"],
    mobile_notification_settings,
    email_notification_settings,
    ["notification_sound"]
);

exports.all_notification_settings = other_notification_settings.concat(
    pm_mention_notification_settings,
    exports.stream_notification_settings
);


function get_notifications_table_row_data(notify_settings) {
    return general_notifications_table_columns.map((column, index) => {
        const setting_name = notify_settings[index];
        if (setting_name === undefined) {
            return {
                setting_name: "",
                is_disabled: true,
                is_checked: false,
            };
        }
        const checkbox = {
            setting_name: setting_name,
            is_disabled: false,
        };
        if (column === "mobile") {
            checkbox.is_disabled = !page_params.realm_push_notifications_enabled;
        }
        checkbox.is_checked = page_params[setting_name];
        return checkbox;
    });
}

exports.all_notifications = {
    general_settings: [
        {
            label: i18n.t("Streams"),
            notification_settings: get_notifications_table_row_data(
                exports.stream_notification_settings),
        },
        {
            label: i18n.t("PMs, mentions, and alerts"),
            notification_settings: get_notifications_table_row_data(
                pm_mention_notification_settings),
        },
    ],
    settings: {
        desktop_notification_settings: desktop_notification_settings,
        mobile_notification_settings: mobile_notification_settings,
        email_notification_settings: email_notification_settings,
    },
    show_push_notifications_tooltip: {
        enable_online_push_notifications: !page_params.realm_push_notifications_enabled,
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
    const data = {};
    data[setting] = JSON.stringify(setting_data);
    settings_ui.do_settings_change(channel.patch, '/json/settings/notifications', data, status_element);
}

function update_desktop_icon_count_display() {
    $("#desktop_icon_count_display").val(page_params.desktop_icon_count_display);
    const count = unread.get_notifiable_count();
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
    $('#notification-settings').on('change', 'input, select', function (e) {
        e.preventDefault();
        e.stopPropagation();
        const input_elem = $(e.currentTarget);
        const setting_name = input_elem.attr("name");
        change_notification_setting(setting_name,
                                    settings_org.get_input_element_value(this),
                                    input_elem.closest('.subsection-parent').find('.alert-notification'));
    });

    update_desktop_icon_count_display();

    $("#play_notification_sound").click(function () {
        $("#notifications-area").find("audio")[0].play();
    });

    const notification_sound_dropdown = $("#notification_sound");
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
    for (const setting of exports.all_notification_settings) {
        if (setting === 'enable_offline_push_notifications'
            && !page_params.realm_push_notifications_enabled) {
            // If push notifications are disabled at the realm level,
            // we should just leave the checkbox always off.
            continue;
        } else if (setting === 'desktop_icon_count_display') {
            update_desktop_icon_count_display();
            continue;
        }

        $("#" + setting).prop('checked', page_params[setting]);
    }
};

window.settings_notifications = exports;
