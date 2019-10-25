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

exports.demote_inactive_streams_values = {
    automatic: {
        code: 1,
        description: i18n.t("Automatic"),
    },
    always: {
        code: 2,
        description: i18n.t("Always"),
    },
    never: {
        code: 3,
        description: i18n.t("Never"),
    },
};

exports.all_display_settings = {
    settings: {
        user_display_settings: [
            "dense_mode",
            "night_mode",
            "high_contrast_mode",
            "left_side_userlist",
            "starred_message_counts",
            "fluid_layout_width",
        ],
    },
    render_only: {
        high_contrast_mode: page_params.development_environment,
        dense_mode: page_params.development_environment,
    },
};

exports.set_up = function () {
    meta.loaded = true;
    $("#display-settings-status").hide();

    $("#user_timezone").val(page_params.timezone);

    $("#demote_inactive_streams").val(page_params.demote_inactive_streams);

    $(".emojiset_choice[value=" + page_params.emojiset + "]").prop("checked", true);

    $("#default_language_modal [data-dismiss]").click(function () {
        overlays.close_modal('default_language_modal');
    });

    _.each(exports.all_display_settings.settings.user_display_settings, function (setting) {
        $("#" + setting).change(function () {
            var data = {};
            data[setting] = JSON.stringify($(this).prop('checked'));

            if (["left_side_userlist"].indexOf(setting) > -1) {
                change_display_setting(
                    data,
                    "#display-settings-status",
                    i18n.t("Saved. Please <a class='reload_link'>reload</a> for the change to take effect."), true);
            } else {
                change_display_setting(data, "#display-settings-status");
            }
        });
    });

    $("#default_language_modal .language").click(function (e) {
        e.preventDefault();
        e.stopPropagation();
        overlays.close_modal('default_language_modal');

        var $link = $(e.target).closest("a[data-code]");
        var setting_value = $link.attr('data-code');
        var data = {default_language: JSON.stringify(setting_value)};

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

    $('#demote_inactive_streams').change(function () {
        var data = {demote_inactive_streams: this.value};
        change_display_setting(data, '#display-settings-status');
    });

    $('body').on('click', '.reload_link', function () {
        window.location.reload();
    });

    $("#twenty_four_hour_time").change(function () {
        var data = {twenty_four_hour_time: JSON.stringify(this.checked)};
        change_display_setting(data, '#time-settings-status');
    });

    $("#user_timezone").change(function () {
        var data = {timezone: JSON.stringify(this.value)};
        change_display_setting(data, '#time-settings-status');
    });
    $(".emojiset_choice").click(function () {
        var data = {emojiset: JSON.stringify($(this).val())};
        var spinner = $("#emoji-settings-status").expectOne();
        loading.make_indicator(spinner, {text: settings_ui.strings.saving });

        channel.patch({
            url: '/json/settings/display',
            data: data,
            success: function () {
            },
            error: function (xhr) {
                ui_report.error(settings_ui.strings.failure, xhr, $('#emoji-settings-status').expectOne());
            },
        });
    });

    $("#translate_emoticons").change(function () {
        var data = {translate_emoticons: JSON.stringify(this.checked)};
        change_display_setting(data, '#emoji-settings-status');
    });
};

exports.report_emojiset_change = function () {
    // TODO: Clean up how this works so we can use
    // change_display_setting.  The challenge is that we don't want to
    // report success before the server_events request returns that
    // causes the actual sprite sheet to change.  The current
    // implementation is wrong, though, in that it displays the UI
    // update in all active browser windows.
    function emoji_success() {
        if ($("#emoji-settings-status").length) {
            loading.destroy_indicator($("#emojiset_spinner"));
            $("#emojiset_select").val(page_params.emojiset);
            ui_report.success(i18n.t("Emojiset changed successfully!"),
                              $('#emoji-settings-status').expectOne());
            var spinner = $("#emoji-settings-status").expectOne();
            settings_ui.display_checkmark(spinner);
        }
    }

    var emojiset = page_params.emojiset;

    if (page_params.emojiset === 'text') {
        // For `text` emojiset we fallback to `google-blob` emojiset
        // for displaying emojis in emoji picker and typeahead.
        emojiset = 'google-blob';
    }

    var sprite = new Image();
    sprite.onload = function () {
        var sprite_css_href = "/static/generated/emoji/" + emojiset + "-sprite.css";
        $("#emoji-spritesheet").attr('href', sprite_css_href);
        emoji_success();
    };
    sprite.src = "/static/generated/emoji/sheet-" + emojiset + "-64.png";
};

exports.update_page = function () {
    $("#twenty_four_hour_time").prop('checked', page_params.twenty_four_hour_time);
    $("#left_side_userlist").prop('checked', page_params.left_side_userlist);
    $("#default_language_name").text(page_params.default_language_name);
    $("#translate_emoticons").prop('checked', page_params.translate_emoticons);
    $("#night_mode").prop('checked', page_params.night_mode);
    // TODO: Set emojiset selector here.
    // Longer term, we'll want to automate this function
};

window.settings_display = exports;
