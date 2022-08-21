import $ from "jquery";

import render_browse_user_groups_list_item from "../templates/user_group_settings/browse_user_groups_list_item.hbs";
import render_user_group_settings_overlay from "../templates/user_group_settings/user_group_settings_overlay.hbs";

import * as browser_history from "./browser_history";
import * as ListWidget from "./list_widget";
import * as overlays from "./overlays";
import * as people from "./people";
import * as ui from "./ui";
import * as user_groups from "./user_groups";

export function setup_page(callback) {
    function populate_and_fill() {
        const rendered = render_user_group_settings_overlay();

        const $manage_groups_container = ui.get_content_element($("#manage_groups_container"));
        $manage_groups_container.empty();
        $manage_groups_container.append(rendered);

        const $container = $("#manage_groups_container .user-groups-list");
        const user_groups_list = user_groups.get_realm_user_groups();

        ListWidget.create($container, user_groups_list, {
            name: "user-groups-overlay",
            modifier(item) {
                item.is_member = user_groups.is_direct_member_of(
                    people.my_current_user_id(),
                    item.id,
                );
                return render_browse_user_groups_list_item(item);
            },
            $simplebar_container: $container,
        });

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
