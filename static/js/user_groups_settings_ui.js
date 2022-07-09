import $ from "jquery";

import render_browse_user_groups_list_item from "../templates/user_group_settings/browse_user_groups_list_item.hbs";
import render_user_group_settings_overlay from "../templates/user_group_settings/user_group_settings_overlay.hbs";

import * as browser_history from "./browser_history";
import * as ListWidget from "./list_widget";
import * as overlays from "./overlays";
import * as people from "./people";
import * as settings_data from "./settings_data";
import * as ui from "./ui";
import * as user_groups from "./user_groups";

export function set_up_click_handlers() {
    $("#groups_overlay").on("click", ".left #clear_search_group_name", (e) => {
        const $input = $("#groups_overlay .left #search_group_name");
        $input.val("");

        // This is a hack to rerender complete
        // stream list once the text is cleared.
        $input.trigger("input");

        e.stopPropagation();
        e.preventDefault();
    });
}

export function setup_page(callback) {
    function populate_and_fill() {
        const template_data = {
            can_create_or_edit_user_groups: settings_data.user_can_edit_user_groups(),
        };

        const rendered = render_user_group_settings_overlay(template_data);

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
            filter: {
                $element: $("#manage_groups_container .left #search_group_name"),
                predicate(item, value) {
                    return (
                        item &&
                        (item.name.toLocaleLowerCase().includes(value) ||
                            item.description.toLocaleLowerCase().includes(value))
                    );
                },
            },
            $simplebar_container: $container,
        });

        set_up_click_handlers();

        // show the "User group settings" header by default.
        $(".display-type #user_group_settings_title").show();

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
