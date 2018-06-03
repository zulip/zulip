var settings_toggle = (function () {

var exports = {};

var toggler;

exports.highlight_toggle = function (tab_name) {
    if (toggler) {
        toggler.goto(tab_name);
    }
};

exports.initialize = function () {
    toggler = components.toggle({
        values: [
            { label: i18n.t("Settings"), key: "settings" },
            { label: i18n.t("Organization"), key: "organization" },
        ],
        callback: function (name, key) {
            if (key === "organization") {
                settings_panel_menu.show_org_settings();
            } else {
                settings_panel_menu.show_normal_settings();
            }
        },
    });

    $("#settings_overlay_container .tab-container").append(toggler.get());
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = settings_toggle;
}
