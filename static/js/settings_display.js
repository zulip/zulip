var settings_display = (function () {

var exports = {};

var meta = {
    loaded: false,
};

function change_display_setting(data, status_element, success_msg, sticky) {
    var $status_el = $(status_element);
    var status_is_sticky = $status_el.data('is_sticky');
    var display_message = status_is_sticky ? $status_el.data('sticky_msg') : success_msg;
    var opts = {
        success_msg: display_message,
        sticky: status_is_sticky || sticky,
    };

    if (sticky) {
        $status_el.data('is_sticky', true);
        $status_el.data('sticky_msg', success_msg);
    }
    settings_ui.do_settings_change(channel.patch, '/json/settings/display', data, status_element, opts);
}

exports.set_night_mode = function (bool) {
    var night_mode = bool;
    var data = {night_mode: JSON.stringify(night_mode)};
    change_display_setting(data, '#display-settings-status');
};

exports.set_up = function () {
    meta.loaded = true;
    $("#display-settings-status").hide();

    $("#user_timezone").val(page_params.timezone);

    // $(".emojiset_choice[value=" + page_params.emojiset + "]").prop("checked", true);
    $("#translate_emoji_to_text").prop('checked', page_params.emojiset === "text");

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

        change_display_setting(data, '#language-settings-status',
                               i18n.t("Saved. Please <a class='reload_link'>reload</a> for the change to take effect."), true);

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
        change_display_setting(data, '#display-settings-status');
    });

    $("#dense_mode").change(function () {
        var dense_mode = this.checked;
        var data = {};
        data.dense_mode = JSON.stringify(dense_mode);
        change_display_setting(data, '#display-settings-status');
    });

    $("#night_mode").change(function () {
        exports.set_night_mode(this.checked);
    });

    $('body').on('click', '.reload_link', function () {
        window.location.reload();
    });

    $("#left_side_userlist").change(function () {
        var left_side_userlist = this.checked;
        var data = {};
        data.left_side_userlist = JSON.stringify(left_side_userlist);
        change_display_setting(data, '#display-settings-status',
                               i18n.t("Saved. Please <a class='reload_link'>reload</a> for the change to take effect."), true);
    });

    $("#twenty_four_hour_time").change(function () {
        var data = {};
        var setting_value = $("#twenty_four_hour_time").is(":checked");
        data.twenty_four_hour_time = JSON.stringify(setting_value);
        change_display_setting(data, '#time-settings-status');
    });

    $("#user_timezone").change(function () {
        var data = {};
        var timezone = this.value;
        data.timezone = JSON.stringify(timezone);
        change_display_setting(data, '#time-settings-status');
    });

    $("#translate_emoji_to_text").change(function () {
        var data = {};
        var is_checked = $("#translate_emoji_to_text").is(":checked");
        if (is_checked) {
            data.emojiset = JSON.stringify("text");
        } else {
            data.emojiset = JSON.stringify("google");
        }
        change_display_setting(data, '#emoji-settings-status');
    });

    $("#translate_emoticons").change(function () {
        var data = {};
        var setting_value = $("#translate_emoticons").is(":checked");
        data.translate_emoticons = JSON.stringify(setting_value);
        change_display_setting(data, '#emoji-settings-status');
    });
};

exports.report_emojiset_change = function () {
    // This function still has full support for multiple emojiset options.
    if (page_params.emojiset === 'text') {
        return;
    }

    var sprite = new Image();
    sprite.onload = function () {
        var sprite_css_href = "/static/generated/emoji/" + page_params.emojiset + "_sprite.css";
        $("#emoji-spritesheet").attr('href', sprite_css_href);
    };
    sprite.src = "/static/generated/emoji/sheet_" + page_params.emojiset + "_64.png";
};

exports.update_page = function () {
    $("#twenty_four_hour_time").prop('checked', page_params.twenty_four_hour_time);
    $("#left_side_userlist").prop('checked', page_params.left_side_userlist);
    $("#default_language_name").text(page_params.default_language_name);
    $("#translate_emoji_to_text").prop('checked', page_params.emojiset === "text");
    $("#translate_emoticons").prop('checked', page_params.translate_emoticons);
    $("#night_mode").prop('checked', page_params.night_mode);
    // Longer term, we'll want to automate this function
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_display;
}
window.settings_display = settings_display;
