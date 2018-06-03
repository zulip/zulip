var settings_toggle = (function () {

var exports = {};

var toggler;

exports.highlight_toggle = function (tab_name) {
    if (toggler) {
        toggler.goto(tab_name, { dont_switch_tab: true });
    }
};

exports.initialize = function () {
    toggler = components.toggle({
        values: [
            { label: i18n.t("Settings"), key: "settings" },
            { label: i18n.t("Organization"), key: "organization" },
        ],
        callback: function (name, key, payload) {
            if (key === "organization") {
                settings_panel_menu.show_org_settings();
                if (!payload.dont_switch_tab) {
                    settings_panel_menu.org_settings.goto_top();
                }
            } else {
                settings_panel_menu.show_normal_settings();
                if (!payload.dont_switch_tab) {
                    settings_panel_menu.normal_settings.goto_top();
                }
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
