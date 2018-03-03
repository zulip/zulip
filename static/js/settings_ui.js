var settings_ui = (function () {

var exports = {};

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
