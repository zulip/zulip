import $ from "jquery";

import * as components from "./components";
import {$t} from "./i18n";
import * as settings_panel_menu from "./settings_panel_menu";

let toggler;

export function highlight_toggle(tab_name) {
    if (toggler) {
        toggler.goto(tab_name);
    }
}

export function initialize() {
    toggler = components.toggle({
        child_wants_focus: true,
        values: [
            {label: $t({defaultMessage: "Personal"}), key: "settings"},
            {label: $t({defaultMessage: "Organization"}), key: "organization"},
        ],
        callback(_name, key) {
            if (key === "organization") {
                settings_panel_menu.show_org_settings();
            } else {
                settings_panel_menu.show_normal_settings();
            }
        },
    });

    settings_panel_menu.set_key_handlers(toggler);

    toggler.get().appendTo("#settings_overlay_container .tab-container");
}

// Handles the collapse/reveal of some tabs in the org settings for non-admins.
export function toggle_org_setting_collapse() {
    const is_collapsed = $(".collapse-org-settings").hasClass("hide-org-settings");
    const show_fewer_settings_text = $t({defaultMessage: "Show fewer"});
    const show_more_settings_text = $t({defaultMessage: "Show more"});

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
    const $current_tab = $(".org-settings-list .active");
    if ($current_tab.hasClass("hide-org-settings")) {
        $(location).attr("href", "/#organization/organization-profile");
    }
}
