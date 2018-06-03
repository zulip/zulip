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
            var normal_list = $('.normal-settings-list');
            var org_list = $('.org-settings-list');

            if (key === "organization") {
                normal_list.hide();
                org_list.show();
                if (!payload.dont_switch_tab) {
                    $("li[data-section='organization-profile']").click();
                }
            } else {
                org_list.hide();
                normal_list.show();
                if (!payload.dont_switch_tab) {
                    $("li[data-section='your-account']").click();
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
