var settings_toggle = (function () {

var exports = {};

var toggler;

exports.highlight_toggle = function (tab_name) {
    if (toggler) {
        toggler.goto(tab_name, { dont_switch_tab: true });
    }
};

exports.create_toggler = function () {
    toggler = components.toggle({
        name: "settings-toggle",
        values: [
            { label: i18n.t("Settings"), key: "settings" },
            { label: i18n.t("Organization"), key: "organization" },
        ],
        callback: function (name, key, payload) {
            $(".sidebar li").hide();

            if (key === "organization") {
                $("li.admin").show();
                if (!payload.dont_switch_tab) {
                    $("li[data-section='organization-profile']").click();
                }
            } else {
                $(".settings-list li:not(.admin)").show();
                if (!payload.dont_switch_tab) {
                    $("li[data-section='your-account']").click();
                }
            }
        },
    });

    $("#settings_overlay_container .tab-container").append(toggler.get());
};

exports.initialize = function () {
    i18n.ensure_i18n(exports.create_toggler);
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = settings_toggle;
}
