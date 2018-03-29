var settings_ui = (function () {

var exports = {};

exports.display_checkmark = function ($elem) {
    var check_mark = document.createElement("img");
    check_mark.src = "/static/images/checkbox-green.svg";
    $elem.prepend(check_mark);
    $(check_mark).css("width", "13px");
};

exports.strings = {};
function _initialize() {
    exports.strings = {
        success: i18n.t("Saved"),
        failure: i18n.t("Save failed"),
        saving: i18n.t("Saving"),
    };

    settings_bots.setup_bot_creation_policy_values();
}

exports.initialize = function () {
    i18n.ensure_i18n(_initialize);
};

// Generic function for informing users about changes to the settings
// UI.  Intended to replace the old system that was built around
// direct calls to `ui_report`.
exports.do_settings_change = function (request_method, url, data, status_element, opts) {
    var spinner = $(status_element).expectOne();
    spinner.fadeTo(0, 1);
    loading.make_indicator(spinner, {text: exports.strings.saving});
    var success_msg;
    var success_continuation;
    var error_continuation;
    var remove_after = 1000;
    var appear_after = 500;

    if (opts !== undefined) {
        success_msg = opts.success_msg;
        success_continuation = opts.success_continuation;
        error_continuation = opts.error_continuation;
        if (opts.sticky) {
            remove_after = null;
        }
    }
    if (success_msg === undefined) {
        success_msg = exports.strings.success;
    }

    request_method({
        url: url,
        data: data,
        success: function (reponse_data) {
            setTimeout(function () {
                ui_report.success(success_msg, spinner, null, remove_after);
                settings_ui.display_checkmark(spinner);
            }, appear_after);
            if (success_continuation !== undefined) {
                success_continuation(reponse_data);
            }
        },
        error: function (xhr) {
            ui_report.error(exports.strings.failure, xhr, spinner);
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
    if ((is_checked && disable_on_uncheck) || (!is_checked && !disable_on_uncheck)) {
        $("#" + sub_setting_id).attr("disabled", false);
        $("#" + sub_setting_id + "_label").parent().removeClass("control-label-disabled");
    } else if ((is_checked && !disable_on_uncheck) || (!is_checked && disable_on_uncheck)) {
        $("#" + sub_setting_id).attr("disabled", "disabled");
        $("#" + sub_setting_id + "_label").parent().addClass("control-label-disabled");
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_ui;
}
