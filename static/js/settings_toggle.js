"use strict";

let toggler;

exports.highlight_toggle = function (tab_name) {
    if (toggler) {
        toggler.goto(tab_name);
    }
};

exports.initialize = function () {
    toggler = components.toggle({
        child_wants_focus: true,
        values: [
            {label: i18n.t("Settings"), key: "settings"},
            {label: i18n.t("Organization"), key: "organization"},
        ],
        callback(name, key) {
            if (key === "organization") {
                settings_panel_menu.show_org_settings();
            } else {
                settings_panel_menu.show_normal_settings();
            }
        },
    });

    settings_panel_menu.set_key_handlers(toggler);

    $("#settings_overlay_container .tab-container").append(toggler.get());
};

// Handles the collapse/reveal of some tabs in the org settings for non-admins.
exports.toggle_org_setting_collapse = function () {
    const is_collapsed = $(".collapse-org-settings").hasClass("hide-org-settings");
    const show_fewer_settings_text = i18n.t("Show fewer");
    const show_more_settings_text = i18n.t("Show more");

    if (is_collapsed) {
        for (const elem of $(".collapse-org-settings")) {
            $(elem).removeClass("hide-org-settings");
        }

        $("#toggle_collapse_chevron").removeClass("fa-angle-double-down");
        $("#toggle_collapse_chevron").addClass("fa-angle-double-up");

        $("#toggle_collapse").text(show_fewer_settings_text);
    } else {
        for (const elem of $(".collapse-org-settings")) {
            $(elem).addClass("hide-org-settings");
        }

        $("#toggle_collapse_chevron").removeClass("fa-angle-double-up");
        $("#toggle_collapse_chevron").addClass("fa-angle-double-down");

        $("#toggle_collapse").text(show_more_settings_text);
    }

    // If current tab is about to be collapsed, go to default tab.
    const current_tab = $(".org-settings-list .active");
    if (current_tab.hasClass("hide-org-settings")) {
        $(location).attr("href", "/#organization/organization-profile");
    }
};

window.settings_toggle = exports;
