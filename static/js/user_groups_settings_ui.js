import $ from "jquery";

import render_browse_user_groups_list_item from "../templates/user_group_settings/browse_user_groups_list_item.hbs";
import render_user_group_settings_overlay from "../templates/user_group_settings/user_group_settings_overlay.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import {$t} from "./i18n";
import * as ListWidget from "./list_widget";
import * as overlays from "./overlays";
import * as people from "./people";
import * as scroll_util from "./scroll_util";
import * as settings_data from "./settings_data";
import * as ui from "./ui";
import * as user_group_create from "./user_group_create";
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

export const show_user_group_settings_pane = {
    nothing_selected() {
        $(".settings, #user-group-creation").hide();
        $(".nothing-selected").show();
        $("#groups_overlay .user-group-info-title").text(
            $t({defaultMessage: "User group settings"}),
        );
    },
    settings(group) {
        $(".settings, #user-group-creation").hide();
        $("#groups_overlay .settings").show();
        $("#groups_overlay .user-group-info-title").text(group.name);
    },
    create_user_group() {
        $(".nothing-selected, .settings, #user-group-creation").hide();
        $("#user-group-creation").show();
        $("#groups_overlay .user-group-info-title").text($t({defaultMessage: "Create user group"}));
    },
};

export function do_open_create_user_group() {
    user_group_create.create_user_group_clicked();
}

export function open_create_user_group() {
    do_open_create_user_group();
    browser_history.update("#groups/new");
}

export function row_for_group_id(group_id) {
    return $(`.group-row[data-group-id='${CSS.escape(group_id)}']`);
}

export function get_active_data() {
    const $active_row = $("div.group-row.active");
    const valid_active_id = Number.parseInt($active_row.attr("data-group-id"), 10);
    const $active_tabs = $(".user-groups-container").find("div.ind-tab.selected");
    return {
        $row: $active_row,
        id: valid_active_id,
        $tabs: $active_tabs,
    };
}

export function switch_to_group_row(group_id) {
    const $group_row = row_for_group_id(group_id);
    const $container = $(".user-groups-list");

    get_active_data().$row.removeClass("active");
    $group_row.addClass("active");

    scroll_util.scroll_element_into_container($group_row, $container);

    // It's dubious that this timeout is needed.
    setTimeout(() => {
        if (group_id === get_active_data().id) {
            $group_row.trigger("click");
        }
    }, 100);
}

function show_right_section() {
    $(".right").addClass("show");
    $(".user-groups-header").addClass("slide-left");
}

export function change_state(section) {
    if (!section) {
        show_user_group_settings_pane.nothing_selected();
        return;
    }
    if (section === "new") {
        do_open_create_user_group();
        return;
    }

    // if the section is a valid number.
    if (/\d+/.test(section)) {
        const group_id = Number.parseInt(section, 10);
        show_right_section();
        switch_to_group_row(group_id);
        return;
    }

    blueslip.warn("invalid section for groups: " + section);
    show_user_group_settings_pane.nothing_selected();
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
        user_group_create.set_up_handlers();

        // show the "User group settings" header by default.
        $(".display-type #user_group_settings_title").show();

        if (callback) {
            callback();
        }
    }

    populate_and_fill();
}

export function initialize() {
    $("#manage_groups_container").on("click", ".create_user_group_button", (e) => {
        e.preventDefault();
        open_create_user_group();
    });

    $("#manage_groups_container").on("click", ".group-row", show_right_section);

    $("#manage_groups_container").on("click", ".fa-chevron-left", () => {
        $(".right").removeClass("show");
        $(".user-groups-header").removeClass("slide-left");
    });
}

export function launch(section) {
    setup_page(() => {
        overlays.open_overlay({
            name: "group_subscriptions",
            $overlay: $("#groups_overlay"),
            on_close() {
                browser_history.exit_overlay();
            },
        });
        change_state(section);
    });
    if (!get_active_data().id) {
        if (section === "new") {
            $("#create_user_group_name").trigger("focus");
        } else {
            $("#search_group_name").trigger("focus");
        }
    }
}
