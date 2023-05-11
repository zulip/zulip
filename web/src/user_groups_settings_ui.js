import $ from "jquery";

import render_browse_user_groups_list_item from "../templates/user_group_settings/browse_user_groups_list_item.hbs";
import render_user_group_settings_overlay from "../templates/user_group_settings/user_group_settings_overlay.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as components from "./components";
import {$t} from "./i18n";
import * as ListWidget from "./list_widget";
import * as overlays from "./overlays";
import * as people from "./people";
import * as scroll_util from "./scroll_util";
import * as settings_data from "./settings_data";
import * as user_group_create from "./user_group_create";
import * as user_group_edit from "./user_group_edit";
import * as user_groups from "./user_groups";

let group_list_widget;
let group_list_toggler;
let active_group_id;

export function set_active_group_id(group_id) {
    active_group_id = group_id;
}

export function reset_active_group_id() {
    active_group_id = undefined;
}

// Ideally this should be included in page params.
// Like we have page_params.max_stream_name_length` and
// `page_params.max_stream_description_length` for streams.
export const max_user_group_name_length = 100;

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
        $("#groups_overlay .settings, #user-group-creation").hide();
        reset_active_group_id();
        $("#groups_overlay .nothing-selected").show();
        $("#groups_overlay .user-group-info-title").text(
            $t({defaultMessage: "User group settings"}),
        );
    },
    settings(group) {
        $("#groups_overlay .nothing-selected, #user-group-creation").hide();
        $("#groups_overlay .settings").show();
        set_active_group_id(group.id);
        $("#groups_overlay .user-group-info-title").text(group.name);
    },
    create_user_group() {
        $("#groups_overlay .nothing-selected, #groups_overlay .settings").hide();
        reset_active_group_id();
        $("#user-group-creation").show();
        $("#groups_overlay .user-group-info-title").text($t({defaultMessage: "Create user group"}));
    },
};

export function do_open_create_user_group() {
    // Only call this directly for hash changes.
    // Prefer open_create_user_group().
    show_right_section();
    user_group_create.create_user_group_clicked();
}

export function open_create_user_group() {
    do_open_create_user_group();
    browser_history.update("#groups/new");
}

export function row_for_group_id(group_id) {
    return $(`.group-row[data-group-id='${CSS.escape(group_id)}']`);
}

export function is_group_already_present(group) {
    return row_for_group_id(group.id).length > 0;
}

export function get_active_data() {
    const $active_tabs = $(".user-groups-container").find("div.ind-tab.selected");
    return {
        $row: row_for_group_id(active_group_id),
        id: active_group_id,
        $tabs: $active_tabs,
    };
}

export function switch_to_group_row(group) {
    if (is_group_already_present(group)) {
        /*
            It is possible that this function may be called at times
            when group-row for concerned group may not be present this
            might occur when user manually edits the url for a group
            that user is not member of and #groups overlay is open with
            your-groups tab active.

            To handle such cases we perform these steps only if the group
            is listed in the left panel else we simply open the settings
            for the concerned group.
        */
        const $group_row = row_for_group_id(group.id);
        const $container = $(".user-groups-list");

        get_active_data().$row.removeClass("active");
        $group_row.addClass("active");

        scroll_util.scroll_element_into_container($group_row, $container);
    }

    user_group_edit.show_group_settings(group);
}

function show_right_section() {
    $(".right").addClass("show");
    $(".user-groups-header").addClass("slide-left");
}

export function add_group_to_table(group) {
    if (is_group_already_present(group)) {
        // If a group is already listed/added in groups modal,
        // then we simply return.
        // This can happen in some corner cases (which might
        // be backend bugs) where a realm administrator may
        // get two user_group-add events.
        return;
    }

    redraw_user_group_list();

    if (user_group_create.get_name() === group.name) {
        // This `user_group_create.get_name()` check tells us whether the
        // group was just created in this browser window; it's a hack
        // to work around the server_events code flow not having a
        // good way to associate with this request because the group
        // ID isn't known yet.
        user_group_edit.show_group_settings(group);
        user_group_create.reset_name();
    }
}

export function update_group(group_id) {
    if (!overlays.groups_open()) {
        return;
    }
    const group = user_groups.get_user_group_from_id(group_id);
    const $group_row = row_for_group_id(group_id);
    // update left side pane
    $group_row.find(".group-name").text(group.name);
    $group_row.find(".description").text(group.description);

    if (get_active_data().id === group.id) {
        // update right side pane
        user_group_edit.update_settings_pane(group);
        // update settings title
        $("#groups_overlay .user-group-info-title").text(group.name);
    }
}

export function change_state(section) {
    if (section === "new") {
        do_open_create_user_group();
        redraw_user_group_list();
        return;
    }

    if (section === "all") {
        group_list_toggler.goto("all-groups");
        return;
    }

    if (section === "your") {
        group_list_toggler.goto("your-groups");
        return;
    }

    // if the section is a valid number.
    if (/\d+/.test(section)) {
        const group_id = Number.parseInt(section, 10);
        const group = user_groups.get_user_group_from_id(group_id);
        if (!group) {
            // Some users can type random url of the form
            // /#groups/<random-group-id> we need to handle that.
            group_list_toggler.goto("your-groups");
        } else {
            show_right_section();
            // We show the list of user groups in the left panel
            // based on the tab that is active. It is `your-groups`
            // tab by default.
            redraw_user_group_list();
            switch_to_group_row(group);
        }
        return;
    }

    blueslip.info("invalid section for groups: " + section);
    group_list_toggler.goto("your-groups");
}

function redraw_left_panel(tab_name) {
    if (tab_name === "all-groups") {
        group_list_widget.replace_list_data(user_groups.get_realm_user_groups());
    } else if (tab_name === "your-groups") {
        group_list_widget.replace_list_data(
            user_groups.get_user_groups_of_user(people.my_current_user_id()),
        );
    }
}

export function redraw_user_group_list() {
    const tab_name = get_active_data().$tabs.first().attr("data-tab-key");
    redraw_left_panel(tab_name);
}

export function switch_group_tab(tab_name) {
    /*
        This switches the groups list tab, but it doesn't update
        the group_list_toggler widget.  You may instead want to
        use `group_list_toggler.goto`.
    */
    redraw_left_panel(tab_name);
    user_group_edit.setup_group_list_tab_hash(tab_name);
}

export function setup_page(callback) {
    function initialize_components() {
        group_list_toggler = components.toggle({
            child_wants_focus: true,
            values: [
                {label: $t({defaultMessage: "Your groups"}), key: "your-groups"},
                {label: $t({defaultMessage: "All groups"}), key: "all-groups"},
            ],
            callback(_label, key) {
                switch_group_tab(key);
            },
        });

        $("#groups_overlay_container .search-container").prepend(group_list_toggler.get());
    }

    function populate_and_fill() {
        const template_data = {
            can_create_or_edit_user_groups: settings_data.user_can_edit_user_groups(),
            max_user_group_name_length,
        };

        const rendered = render_user_group_settings_overlay(template_data);

        const $groups_overlay_container = scroll_util.get_content_element(
            $("#groups_overlay_container"),
        );
        $groups_overlay_container.empty();
        $groups_overlay_container.append(rendered);

        // Initially as the overlay is build with empty right panel,
        // active_group_id is undefined.
        reset_active_group_id();

        const $container = $("#groups_overlay_container .user-groups-list");

        /*
            As change_state function called after this initial build up
            redraws left panel based on active tab we avoid building extra dom
            here as the required group-rows are anyway going to be created
            immediately after this due to call to change_state. So we call
            `ListWidget.create` with empty user groups list.
        */
        group_list_widget = ListWidget.create($container, [], {
            name: "user-groups-overlay",
            get_item: ListWidget.default_get_item,
            modifier_html(item) {
                item.is_member = user_groups.is_direct_member_of(
                    people.my_current_user_id(),
                    item.id,
                );
                return render_browse_user_groups_list_item(item);
            },
            filter: {
                $element: $("#groups_overlay_container .left #search_group_name"),
                predicate(item, value) {
                    return (
                        item &&
                        (item.name.toLocaleLowerCase().includes(value) ||
                            item.description.toLocaleLowerCase().includes(value))
                    );
                },
                onupdate() {
                    if (active_group_id !== undefined) {
                        const active_group = user_groups.get_user_group_from_id(active_group_id);
                        if (is_group_already_present(active_group)) {
                            row_for_group_id(active_group_id).addClass("active");
                        }
                    }
                },
            },
            init_sort: ["alphabetic", "name"],
            $simplebar_container: $container,
        });

        initialize_components();

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
    $("#groups_overlay_container").on("click", ".create_user_group_button", (e) => {
        e.preventDefault();
        open_create_user_group();
    });

    $("#groups_overlay_container").on("click", ".group-row", show_right_section);

    $("#groups_overlay_container").on("click", ".fa-chevron-left", () => {
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
