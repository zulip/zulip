import $ from "jquery";

import render_user_group_settings_overlay from "../templates/user_group_settings/user_group_settings_overlay.hbs";

import * as browser_history from "./browser_history";
import * as overlays from "./overlays";
import * as ui from "./ui";

export function setup_page(callback) {
    function populate_and_fill() {
        const rendered = render_user_group_settings_overlay();

        const $manage_groups_container = ui.get_content_element($("#manage_groups_container"));
        $manage_groups_container.empty();
        $manage_groups_container.append(rendered);

        if (callback) {
            callback();
        }
    }

    populate_and_fill();
}

export function launch() {
    setup_page(() => {
        overlays.open_overlay({
            name: "group_subscriptions",
            $overlay: $("#groups_overlay"),
            on_close() {
                browser_history.exit_overlay();
            },
        });
    });
}
