var settings_lab = (function () {

var exports = {};

exports.set_up = function () {
    $("#ui-settings-status").hide();

    $("#ui-settings .change-setting").change(function (e) {
        e.preventDefault();
        var labs_updates = {};
        _.each(["default_desktop_notifications"],
            function (setting) {
                labs_updates[setting] = $("#" + setting).is(":checked");
            });

            channel.patch({
                url: '/json/settings/ui',
                data: labs_updates,
                success: function () {
                    var message = i18n.t("Updated settings!  You will need to reload for these changes to take effect.", page_params);
                    var ui_settings_status = $('#ui-settings-status').expectOne();

                    ui_report.success(message, ui_settings_status);
                },
                error: function (xhr) {
                    ui_report.error(i18n.t("Error changing settings"), xhr, $('#ui-settings-status').expectOne());
                },
            });
        });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_lab;
}
