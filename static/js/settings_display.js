var settings_display = (function () {

var exports = {};

exports.set_up = function () {
    $("#display-settings-status").hide();

    $("#user_timezone").val(page_params.timezone);
    $("#emojiset_select").val(page_params.emojiset);

    $("#default_language_modal [data-dismiss]").click(function () {
        overlays.close_modal('default_language_modal');
    });

    $("#default_language_modal .language").click(function (e) {
        e.preventDefault();
        e.stopPropagation();
        overlays.close_modal('default_language_modal');

        var data = {};
        var $link = $(e.target).closest("a[data-code]");
        var setting_value = $link.attr('data-code');
        data.default_language = JSON.stringify(setting_value);

        var new_language = $link.attr('data-name');
        $('#default_language_name').text(new_language);

        var context = {};
        context.lang = new_language;

        channel.patch({
            url: '/json/settings/display',
            data: data,
            success: function () {
                ui_report.success(i18n.t("__lang__ is now the default language!  You will need to reload the window for your changes to take effect", context),
                                  $('#display-settings-status').expectOne());
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Error updating default language setting"), xhr, $('#display-settings-status').expectOne());
            },
        });
    });

    $('#default_language').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        overlays.open_modal('default_language_modal');
    });

    $("#high_contrast_mode").change(function () {
        var high_contrast_mode = this.checked;
        var data = {};
        data.high_contrast_mode = JSON.stringify(high_contrast_mode);
        var context = {};
        if (data.high_contrast_mode === "true") {
            context.enabled_or_disabled = i18n.t('Enabled');
        } else {
            context.enabled_or_disabled = i18n.t('Disabled');
        }

        channel.patch({
            url: '/json/settings/display',
            data: data,
            success: function () {
                ui_report.success(i18n.t("High contrast mode __enabled_or_disabled__!", context),
                                  $('#display-settings-status').expectOne());
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Error updating high contrast setting"), xhr, $('#display-settings-status').expectOne());
            },
        });
    });

    $("#left_side_userlist").change(function () {
        var left_side_userlist = this.checked;
        var data = {};
        data.left_side_userlist = JSON.stringify(left_side_userlist);
        var context = {};
        if (data.left_side_userlist === "true") {
            context.side = i18n.t('left');
        } else {
            context.side = i18n.t('right');
        }

        channel.patch({
            url: '/json/settings/display',
            data: data,
            success: function () {
                ui_report.success(i18n.t("User list will appear on the __side__ hand side! You will need to reload the window for your changes to take effect.", context),
                                  $('#display-settings-status').expectOne());
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Error updating user list placement setting"), xhr, $('#display-settings-status').expectOne());
            },
        });
    });

    $("#emoji_alt_code").change(function () {
        var emoji_alt_code = this.checked;
        var data = {};
        data.emoji_alt_code = JSON.stringify(emoji_alt_code);
        var context = {};
        if (data.emoji_alt_code === "true") {
            context.text_or_images = i18n.t('text');
        } else {
            context.text_or_images = i18n.t('images');
        }

        channel.patch({
            url: '/json/settings/display',
            data: data,
            success: function () {
                ui_report.success(i18n.t("Emoji reactions will appear as __text_or_images__!", context),
                                  $('#display-settings-status').expectOne());
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Error updating emoji appearance setting"), xhr, $('#display-settings-status').expectOne());
            },
        });
    });

    $("#twenty_four_hour_time").change(function () {
        var data = {};
        var setting_value = $("#twenty_four_hour_time").is(":checked");
        data.twenty_four_hour_time = JSON.stringify(setting_value);
        var context = {};
        if (data.twenty_four_hour_time === "true") {
            context.format = '24';
        } else {
            context.format = '12';
        }

        channel.patch({
            url: '/json/settings/display',
            data: data,
            success: function () {
                ui_report.success(i18n.t("Time will now be displayed in the __format__-hour format!", context),
                                  $('#display-settings-status').expectOne());
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Error updating time format setting"), xhr, $('#display-settings-status').expectOne());
            },
        });
    });

    $("#user_timezone").change(function () {
        var data = {};
        var timezone = this.value;
        data.timezone = JSON.stringify(timezone);

        channel.patch({
            url: '/json/settings/display',
            data: data,
            success: function () {
                ui_report.success(i18n.t("Your time zone have been set to __timezone__", {timezone: timezone}), $('#display-settings-status').expectOne());
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Error updating time zone"), xhr, $('#display-settings-status').expectOne());
            },
        });
    });

    $("#emojiset_select").change(function () {
        var emojiset = $(this).val();
        var data = {};
        data.emojiset = JSON.stringify(emojiset);

        channel.patch({
            url: '/json/settings/display',
            data: data,
            success: function () {
                var spinner = $("#emojiset_spinner").expectOne();
                loading.make_indicator(spinner, {text: 'Changing emojiset.'});
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Error changing emojiset."), xhr, $('#display-settings-status').expectOne());
            },
        });
    });
};

function _update_page() {
    $("#twenty_four_hour_time").prop('checked', page_params.twenty_four_hour_time);
    $("#left_side_userlist").prop('checked', page_params.left_side_userlist);
    $("#emoji_alt_code").prop('checked', page_params.emoji_alt_code);
    $("#default_language_name").text(page_params.default_language_name);
}

exports.update_page = function () {
    i18n.ensure_i18n(_update_page);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_display;
}
