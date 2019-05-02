var stream_ui_updates = (function () {

var exports = {};

exports.update_check_button_for_sub = function (sub) {
    var button = subs.check_button_for_sub(sub);
    if (sub.subscribed) {
        button.addClass("checked");
    } else {
        button.removeClass("checked");
    }
};

exports.update_settings_button_for_sub = function (sub) {
    var settings_button = subs.settings_button_for_sub(sub);
    if (sub.subscribed) {
        settings_button.text(i18n.t("Unsubscribe")).removeClass("unsubscribed");
    } else {
        settings_button.text(i18n.t("Subscribe")).addClass("unsubscribed");
    }
    if (sub.should_display_subscription_button) {
        settings_button.show();
    } else {
        settings_button.hide();
    }
};

exports.update_regular_sub_settings = function (sub) {
    if (!stream_edit.is_sub_settings_active(sub)) {
        return;
    }
    var $settings = $(".subscription_settings[data-stream-id='" + sub.stream_id + "']");
    if (sub.subscribed) {
        if ($settings.find(".email-address").val().length === 0) {
            // Rerender stream email address, if not.
            $settings.find(".email-address").text(sub.email_address);
            $settings.find(".stream-email-box").show();
        }
        $settings.find(".regular_subscription_settings").addClass('in');
    } else {
        $settings.find(".regular_subscription_settings").removeClass('in');
        // Clear email address widget
        $settings.find(".email-address").html("");
    }
};

exports.update_change_stream_privacy_settings = function (sub) {
    var stream_privacy_btn = $(".change-stream-privacy");

    if (sub.can_change_stream_permissions) {
        stream_privacy_btn.show();
    } else {
        stream_privacy_btn.hide();
    }
};

exports.update_stream_row_in_settings_tab = function (sub) {
    // This function display/hide stream row in stream settings tab,
    // used to display immediate effect of add/removal subscription event.
    // If user is subscribed to stream, it will show sub row under
    // "Subscribed" tab, otherwise if stream is not public hide
    // stream row under tab.
    if (subs.is_subscribed_stream_tab_active()) {
        var sub_row = subs.row_for_stream_id(sub.stream_id);
        if (sub.subscribed) {
            sub_row.removeClass("notdisplayed");
        } else if (sub.invite_only) {
            sub_row.addClass("notdisplayed");
        }
    }
};

exports.update_stream_privacy = function (sub) {
    var stream_settings = stream_edit.settings_for_sub(sub);
    var sub_row = subs.row_for_stream_id(sub.stream_id);
    var html;

    stream_data.update_calculated_fields(sub);

    html = templates.render('subscription_setting_icon', sub);
    sub_row.find('.icon').expectOne().replaceWith($(html));

    html = templates.render('subscription_type', sub);
    stream_settings.find('.subscription-type-text').expectOne().html(html);

    if (sub.invite_only) {
        stream_settings.find(".large-icon")
            .removeClass("hash").addClass("lock")
            .html("<i class='fa fa-lock' aria-hidden='true'></i>");
    } else {
        stream_settings.find(".large-icon")
            .addClass("hash").removeClass("lock")
            .html("");
    }

    stream_list.redraw_stream_privacy(sub);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = stream_ui_updates;
}
window.stream_ui_updates = stream_ui_updates;
