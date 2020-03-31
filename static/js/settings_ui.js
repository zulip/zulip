exports.display_checkmark = function ($elem) {
    const check_mark = document.createElement("img");
    check_mark.src = "/static/images/checkbox-green.svg";
    $elem.prepend(check_mark);
    $(check_mark).css("width", "13px");
};

exports.strings = {
    success: i18n.t("Saved"),
    failure: i18n.t("Save failed"),
    saving: i18n.t("Saving"),
};

// Generic function for informing users about changes to the settings
// UI.  Intended to replace the old system that was built around
// direct calls to `ui_report`. The opts paremeter with_button decides
// whether a spinner or a save_discard_button is to be used to display
// the status messages.
exports.do_settings_change = function (request_method, url, data, status_element, opts) {
    let success_msg;
    let success_continuation;
    let error_continuation;
    let remove_after;
    const appear_after = 500;
    let with_button;
    let spinner;
    let save_button_save_state;
    let save_button_div;
    let discard_button;
    let save_btn;
    let textEl;

    if (opts !== undefined) {
        success_msg = opts.success_msg;
        success_continuation = opts.success_continuation;
        error_continuation = opts.error_continuation;
        with_button = opts.with_button;
        if (opts.sticky) {
            remove_after = null;
        }
    }
    if (success_msg === undefined) {
        success_msg = exports.strings.success;
    }

    if (with_button) {
        save_button_save_state = settings_org.change_save_button_state;
        save_button_div = $(status_element).find(".save-button-controls");
        discard_button = $(status_element).find(".discard-button");
        save_btn = $(status_element).find(".save-button");
        textEl = save_btn.find('.icon-button-text');
        discard_button.addClass("hide");
        save_button_div.removeClass('hide').addClass('show').fadeIn(300);
        save_button_save_state(save_button_div, "saving");
    } else {
        remove_after = 1000;
        spinner = $(status_element).expectOne();
        spinner.fadeTo(0, 1);
        loading.make_indicator(spinner, {text: exports.strings.saving});
    }

    request_method({
        url: url,
        data: data,
        success: function (reponse_data) {
            if (with_button) {
                save_button_save_state(save_button_div, "succeeded");
                if (opts !== undefined && opts.success_msg) {
                    textEl.text(opts.success_msg).fadeIn(0);
                }
            } else {
                setTimeout(function () {
                    ui_report.success(success_msg, spinner, remove_after);
                    exports.display_checkmark(spinner);
                }, appear_after);
            }
            if (success_continuation !== undefined) {
                if (opts !== undefined && opts.success_continuation_arg) {
                    success_continuation(opts.success_continuation_arg);
                } else {
                    success_continuation(reponse_data);
                }
            }
        },
        error: function (xhr) {
            if (with_button) {
                save_button_save_state(save_button_div, "failed");
                save_button_div.addClass("hide");
                if (opts !== undefined && opts.error_msg_element) {
                    ui_report.error(exports.strings.failure, xhr, opts.error_msg_element);
                }
            } else {
                if (opts !== undefined && opts.error_msg_element) {
                    loading.destroy_indicator(spinner);
                    ui_report.error(exports.strings.failure, xhr, opts.error_msg_element);
                } else {
                    ui_report.error(exports.strings.failure, xhr, spinner);
                }
            }
            if (error_continuation !== undefined) {
                error_continuation(xhr);
            }
        },
    });
};

// This function is used to disable sub-setting when main setting is checked or unchecked
// or two settings are inter-dependent on their values values.
// * is_checked is boolean, shows if the main setting is checked or not.
// * sub_setting_id is sub setting or setting which depend on main setting,
//   string id of setting.
// * disable_on_uncheck is boolean, true if sub setting should be disabled
//   when main setting unchecked.
exports.disable_sub_setting_onchange = function (is_checked, sub_setting_id, disable_on_uncheck) {
    if (is_checked && disable_on_uncheck || !is_checked && !disable_on_uncheck) {
        $("#" + sub_setting_id).attr("disabled", false);
        $("#" + sub_setting_id + "_label").parent().removeClass("control-label-disabled");
    } else if (is_checked && !disable_on_uncheck || !is_checked && disable_on_uncheck) {
        $("#" + sub_setting_id).attr("disabled", "disabled");
        $("#" + sub_setting_id + "_label").parent().addClass("control-label-disabled");
    }
};

window.settings_ui = exports;
