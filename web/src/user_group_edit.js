import $ from "jquery";

import render_confirm_delete_user from "../templates/confirm_dialog/confirm_delete_user.hbs";
import render_browse_user_groups_list_item from "../templates/user_group_settings/browse_user_groups_list_item.hbs";
import render_change_user_group_info_modal from "../templates/user_group_settings/change_user_group_info_modal.hbs";
import render_user_group_settings from "../templates/user_group_settings/user_group_settings.hbs";
import render_user_group_settings_overlay from "../templates/user_group_settings/user_group_settings_overlay.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as channel from "./channel";
import * as components from "./components";
import * as confirm_dialog from "./confirm_dialog";
import * as dialog_widget from "./dialog_widget";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import * as overlays from "./overlays";
import * as people from "./people";
import * as scroll_util from "./scroll_util";
import * as settings_components from "./settings_components";
import * as settings_data from "./settings_data";
import * as settings_org from "./settings_org";
import {current_user, realm} from "./state_data";
import * as ui_report from "./ui_report";
import * as user_group_components from "./user_group_components";
import * as user_group_create from "./user_group_create";
import * as user_group_edit_members from "./user_group_edit_members";
import * as user_groups from "./user_groups";
import * as util from "./util";

export let toggler;
export let select_tab = "general";

let group_list_widget;
let group_list_toggler;
let active_group_id;

function get_user_group_id(target) {
    const $row = $(target).closest(
        ".group-row, .user_group_settings_wrapper, .save-button, .group_settings_header",
    );
    return Number.parseInt($row.attr("data-group-id"), 10);
}

function get_user_group_for_target(target) {
    const user_group_id = get_user_group_id(target);
    if (!user_group_id) {
        blueslip.error("Cannot find user group id for target");
        return undefined;
    }

    const group = user_groups.get_user_group_from_id(user_group_id);
    if (!group) {
        blueslip.error("get_user_group_for_target() failed id lookup", {user_group_id});
        return undefined;
    }
    return group;
}

export function get_edit_container(group) {
    return $(
        `#groups_overlay .user_group_settings_wrapper[data-group-id='${CSS.escape(group.id)}']`,
    );
}

function update_add_members_elements(group) {
    if (!is_editing_group(group.id)) {
        return;
    }

    // We are only concerned with the Members tab for editing groups.
    const $add_members_container = $(".edit_members_for_user_group .add_members_container");

    if (current_user.is_guest || realm.realm_is_zephyr_mirror_realm) {
        // For guest users, we just hide the add_members feature.
        $add_members_container.hide();
        return;
    }

    // Otherwise, we adjust whether the widgets are disabled based on
    // whether this user is authorized to add members.
    const $input_element = $add_members_container.find(".input").expectOne();
    const $button_element = $add_members_container.find('button[name="add_member"]').expectOne();

    if (settings_data.can_edit_user_group(group.id)) {
        $input_element.prop("contenteditable", true);
        $button_element.prop("disabled", false);
        $button_element.css("pointer-events", "");
        $add_members_container[0]._tippy?.destroy();
        $add_members_container.removeClass("add_members_disabled");
    } else {
        $input_element.prop("contenteditable", false);
        $button_element.prop("disabled", true);
        $add_members_container.addClass("add_members_disabled");

        settings_components.initialize_disable_btn_hint_popover(
            $add_members_container,
            $t({defaultMessage: "Only group members can add users to a group."}),
        );
    }
}

function show_membership_settings(group) {
    const $edit_container = get_edit_container(group);
    update_add_members_elements(group);

    const $member_container = $edit_container.find(".edit_members_for_user_group");
    user_group_edit_members.enable_member_management({
        group,
        $parent_container: $member_container,
    });
}

function enable_group_edit_settings(group) {
    if (!is_editing_group(group.id)) {
        return;
    }
    const $edit_container = get_edit_container(group);
    $edit_container.find(".group-header .button-group").show();
    $edit_container.find(".member-list .actions").show();
    update_add_members_elements(group);
}

function disable_group_edit_settings(group) {
    if (!is_editing_group(group.id)) {
        return;
    }
    const $edit_container = get_edit_container(group);
    $edit_container.find(".group-header .button-group").hide();
    $edit_container.find(".member-list .user-remove-actions").hide();
    update_add_members_elements(group);
}

function group_membership_button(group_id) {
    return $(`.group_settings_header[data-group-id='${CSS.escape(group_id)}'] .join_leave_button`);
}

function initialize_tooltip_for_membership_button(group_id) {
    const $tooltip_wrapper = group_membership_button(group_id).closest(
        ".join_leave_button_wrapper",
    );
    const is_member = user_groups.is_user_in_group(group_id, people.my_current_user_id());
    let tooltip_message;
    if (is_member) {
        tooltip_message = $t({defaultMessage: "You do not have permission to leave this group."});
    } else {
        tooltip_message = $t({defaultMessage: "You do not have permission to join this group."});
    }
    settings_components.initialize_disable_btn_hint_popover($tooltip_wrapper, tooltip_message);
}

function update_group_membership_button(group_id) {
    const $group_settings_button = group_membership_button(group_id);

    if (!$group_settings_button.length) {
        return;
    }

    const is_member = user_groups.is_user_in_group(group_id, people.my_current_user_id());
    if (is_member) {
        $group_settings_button.text($t({defaultMessage: "Leave group"}));
    } else {
        $group_settings_button.text($t({defaultMessage: "Join group"}));
    }

    if (settings_data.can_edit_user_group(group_id)) {
        $group_settings_button.prop("disabled", false);
        $group_settings_button.css("pointer-events", "");
    } else {
        $group_settings_button.prop("disabled", true);
        initialize_tooltip_for_membership_button(group_id);
    }
}

export function handle_member_edit_event(group_id, user_ids) {
    if (!overlays.groups_open()) {
        return;
    }
    const group = user_groups.get_user_group_from_id(group_id);

    // update members list if currently rendered.
    if (is_editing_group(group_id)) {
        user_group_edit_members.update_member_list_widget(group);
        if (user_ids.includes(people.my_current_user_id())) {
            update_group_membership_button(group_id);
        }
    }

    // update display of group-rows on left panel.
    // We need this update only if your-groups tab is active
    // and current user is among the affect users as in that
    // case the group widget list need to be updated and show
    // or remove the group-row on the left panel accordingly.
    const tab_key = get_active_data().$tabs.first().attr("data-tab-key");
    if (tab_key === "your-groups" && user_ids.includes(people.my_current_user_id())) {
        if (user_groups.is_user_in_group(group_id, people.my_current_user_id())) {
            // We add the group row to list if the current user
            // is added to it. The whole list is redrawed to
            // maintain the sorted order of groups.
            redraw_user_group_list();
        } else if (!settings_data.can_edit_user_group(group_id)) {
            // We remove the group row immediately only if the
            // user cannot join the group again themselves.
            const group_row = row_for_group_id(group_id);
            if (group_row.length) {
                group_row.remove();
                update_empty_left_panel_message();
            }
        }
    }

    // update display of check-mark.
    if (is_group_already_present(group)) {
        const $row = row_for_group_id(group_id);

        const item = group;
        item.is_member = user_groups.is_user_in_group(group_id, people.my_current_user_id());
        item.can_edit = settings_data.can_edit_user_group(item.id);
        const html = render_browse_user_groups_list_item(item);
        const $new_row = $(html);

        // TODO: Remove this if/when we just handle "active" when rendering templates.
        if ($row.hasClass("active")) {
            $new_row.addClass("active");
        }

        $row.replaceWith($new_row);
    }

    if (
        !is_editing_group(group_id) &&
        user_ids.includes(people.my_current_user_id()) &&
        user_groups.is_user_in_group(group_id, people.my_current_user_id())
    ) {
        const $group_row = row_for_group_id(group.id);
        open_group_edit_panel_for_row($group_row);
    }

    // update_settings buttons.
    if (settings_data.can_edit_user_group(group_id)) {
        enable_group_edit_settings(group);
    } else {
        disable_group_edit_settings(group);
    }
}

export function update_settings_pane(group) {
    const $edit_container = get_edit_container(group);
    $edit_container.find(".group-name").text(group.name);
    $edit_container.find(".group-description").text(group.description);

    settings_org.discard_property_element_changes(
        $("#id_can_mention_group"),
        false,
        undefined,
        group,
    );
}

function update_toggler_for_group_setting() {
    toggler.goto(select_tab);
}

export function show_settings_for(group) {
    const html = render_user_group_settings({
        group,
        can_edit: settings_data.can_edit_user_group(group.id),
        is_member: user_groups.is_direct_member_of(people.my_current_user_id(), group.id),
    });

    scroll_util.get_content_element($("#user_group_settings")).html(html);
    update_toggler_for_group_setting();

    if (!settings_data.can_edit_user_group(group.id)) {
        initialize_tooltip_for_membership_button(group.id);
    }

    toggler.get().prependTo("#user_group_settings .tab-container");
    const $edit_container = get_edit_container(group);
    $(".nothing-selected").hide();

    $edit_container.show();
    show_membership_settings(group);
    user_group_components.setup_permissions_dropdown(group, false);
}

export function setup_group_settings(group) {
    toggler = components.toggle({
        child_wants_focus: true,
        values: [
            {label: $t({defaultMessage: "General"}), key: "general"},
            {label: $t({defaultMessage: "Members"}), key: "members"},
        ],
        callback(_name, key) {
            $(".group_setting_section").hide();
            $(`[data-group-section="${CSS.escape(key)}"]`).show();
            select_tab = key;
            const hash = hash_util.group_edit_url(group, select_tab);
            browser_history.update(hash);
        },
    });

    show_settings_for(group);
}

export function setup_group_list_tab_hash(tab_key_value) {
    /*
        We do not update the hash based on tab switches if
        a group is currently being edited.
    */
    if (get_active_data().id !== undefined) {
        return;
    }

    if (tab_key_value === "all-groups") {
        browser_history.update("#groups/all");
    } else if (tab_key_value === "your-groups") {
        browser_history.update("#groups/your");
    } else {
        blueslip.debug(`Unknown tab_key_value: ${tab_key_value} for groups overlay.`);
    }
}

function display_membership_toggle_spinner(group_row) {
    /* Prevent sending multiple requests by removing the button class. */
    $(group_row).find(".check").removeClass("join_leave_button");

    /* Hide the tick. */
    const $tick = $(group_row).find("svg");
    $tick.addClass("hide");

    /* Add a spinner to show the request is in process. */
    const $spinner = $(group_row).find(".join_leave_status").expectOne();
    $spinner.show();
    loading.make_indicator($spinner);
}

function hide_membership_toggle_spinner(group_row) {
    /* Re-enable the button to handle requests. */
    $(group_row).find(".check").addClass("join_leave_button");

    /* Show the tick. */
    const $tick = $(group_row).find("svg");
    $tick.removeClass("hide");

    /* Destroy the spinner. */
    const $spinner = $(group_row).find(".join_leave_status").expectOne();
    loading.destroy_indicator($spinner);
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

function empty_right_panel() {
    $(".group-row.active").removeClass("active");
    show_user_group_settings_pane.nothing_selected();
}

function open_right_panel_empty() {
    empty_right_panel();
    const tab_key = $(".user-groups-container")
        .find("div.ind-tab.selected")
        .first()
        .attr("data-tab-key");
    setup_group_list_tab_hash(tab_key);
}

export function is_editing_group(desired_group_id) {
    if (!overlays.groups_open()) {
        return false;
    }
    return get_active_data().id === desired_group_id;
}

export function handle_deleted_group(group_id) {
    if (!overlays.groups_open()) {
        return;
    }

    if (is_editing_group(group_id)) {
        open_right_panel_empty();
    }
    redraw_user_group_list();
}

export function show_group_settings(group) {
    $(".group-row.active").removeClass("active");
    show_user_group_settings_pane.settings(group);
    row_for_group_id(group.id).addClass("active");
    setup_group_settings(group);
}

export function open_group_edit_panel_for_row(group_row) {
    const group = get_user_group_for_target(group_row);
    show_group_settings(group);
}

export function set_active_group_id(group_id) {
    active_group_id = group_id;
}

export function reset_active_group_id() {
    active_group_id = undefined;
}

// Ideally this should be included in page params.
// Like we have realm.max_stream_name_length` and
// `realm.max_stream_description_length` for streams.
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

function create_user_group_clicked() {
    // this changes the tab switcher (settings/preview) which isn't necessary
    // to a add new stream title.
    show_user_group_settings_pane.create_user_group();
    $(".group-row.active").removeClass("active");

    user_group_create.show_new_user_group_modal();
    $("#create_user_group_name").trigger("focus");
}

export function do_open_create_user_group() {
    // Only call this directly for hash changes.
    // Prefer open_create_user_group().
    show_right_section();
    create_user_group_clicked();
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

    show_group_settings(group);
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
        show_group_settings(group);
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
        update_settings_pane(group);
        // update settings title
        $("#groups_overlay .user-group-info-title").text(group.name);
    }
}

export function change_state(section, left_side_tab, right_side_tab) {
    if (section === "new") {
        do_open_create_user_group();
        redraw_user_group_list();
        return;
    }

    if (section === "all") {
        group_list_toggler.goto("all-groups");
        empty_right_panel();
        return;
    }

    // if the section is a valid number.
    if (/\d+/.test(section)) {
        const group_id = Number.parseInt(section, 10);
        const group = user_groups.get_user_group_from_id(group_id);
        show_right_section();
        select_tab = right_side_tab;

        if (left_side_tab === undefined) {
            left_side_tab = "all-groups";
            if (user_groups.is_direct_member_of(current_user.user_id, group_id)) {
                left_side_tab = "your-groups";
            }
        }

        // Callback to .goto() will update browser_history unless a
        // group is being edited. We are always editing a group here
        // so its safe to call
        if (left_side_tab !== group_list_toggler.value()) {
            set_active_group_id(group.id);
            group_list_toggler.goto(left_side_tab);
        }
        switch_to_group_row(group);
        return;
    }

    group_list_toggler.goto("your-groups");
    empty_right_panel();
}

function compare_by_name(a, b) {
    return util.strcmp(a.name, b.name);
}

function redraw_left_panel(tab_name) {
    let groups_list_data;
    if (tab_name === "all-groups") {
        groups_list_data = user_groups.get_realm_user_groups();
    } else if (tab_name === "your-groups") {
        groups_list_data = user_groups.get_user_groups_of_user(people.my_current_user_id());
    }
    groups_list_data.sort(compare_by_name);
    group_list_widget.replace_list_data(groups_list_data);
    update_empty_left_panel_message();
    maybe_reset_right_panel(groups_list_data);
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
    setup_group_list_tab_hash(tab_name);
}

export function add_or_remove_from_group(group, group_row) {
    const user_id = people.my_current_user_id();
    function success_callback() {
        if (group_row.length) {
            hide_membership_toggle_spinner(group_row);
        }
    }

    function error_callback() {
        if (group_row.length) {
            hide_membership_toggle_spinner(group_row);
        }
    }

    if (group_row.length) {
        display_membership_toggle_spinner(group_row);
    }
    if (user_groups.is_direct_member_of(user_id, group.id)) {
        user_group_edit_members.edit_user_group_membership({
            group,
            removed: [user_id],
            success_callback,
            error_callback,
        });
    } else {
        user_group_edit_members.edit_user_group_membership({
            group,
            added: [user_id],
            success_callback,
            error_callback,
        });
    }
}

export function maybe_reset_right_panel(groups_list_data) {
    if (active_group_id === undefined) {
        return;
    }

    const group_ids = new Set(groups_list_data.map((group) => group.id));
    if (!group_ids.has(active_group_id)) {
        show_user_group_settings_pane.nothing_selected();
    }
}

export function update_empty_left_panel_message() {
    // Check if we have any groups in panel to decide whether to
    // display a notice.
    let has_groups;
    const is_your_groups_tab_active =
        get_active_data().$tabs.first().attr("data-tab-key") === "your-groups";
    if (is_your_groups_tab_active) {
        has_groups = user_groups.get_user_groups_of_user(people.my_current_user_id()).length;
    } else {
        has_groups = user_groups.get_realm_user_groups().length;
    }
    if (has_groups) {
        $(".no-groups-to-show").hide();
        return;
    }
    if (is_your_groups_tab_active) {
        $(".all_groups_tab_empty_text").hide();
        $(".your_groups_tab_empty_text").show();
    } else {
        $(".your_groups_tab_empty_text").hide();
        $(".all_groups_tab_empty_text").show();
    }
    $(".no-groups-to-show").show();
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

        group_list_toggler.get().prependTo("#groups_overlay_container .list-toggler-container");
    }

    function populate_and_fill() {
        const template_data = {
            can_create_or_edit_user_groups: settings_data.user_can_edit_user_groups(),
            max_user_group_name_length,
        };

        const groups_overlay_html = render_user_group_settings_overlay(template_data);

        const $groups_overlay_container = scroll_util.get_content_element(
            $("#groups_overlay_container"),
        );
        $groups_overlay_container.html(groups_overlay_html);

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
                item.can_edit = settings_data.can_edit_user_group(item.id);
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
    $("#groups_overlay_container").on("click", ".group-row", function (e) {
        if ($(e.target).closest(".check, .user_group_settings_wrapper").length === 0) {
            open_group_edit_panel_for_row(this);
        }
    });

    $("#groups_overlay_container").on("click", "#open_group_info_modal", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const user_group_id = get_user_group_id(e.target);
        const user_group = user_groups.get_user_group_from_id(user_group_id);
        const template_data = {
            group_name: user_group.name,
            group_description: user_group.description,
            max_user_group_name_length,
        };
        const change_user_group_info_modal = render_change_user_group_info_modal(template_data);
        dialog_widget.launch({
            html_heading: $t_html(
                {defaultMessage: "Edit {group_name}"},
                {group_name: user_group.name},
            ),
            html_body: change_user_group_info_modal,
            id: "change_group_info_modal",
            loading_spinner: true,
            on_click: save_group_info,
            post_render() {
                $("#change_group_info_modal .dialog_submit_button")
                    .addClass("save-button")
                    .attr("data-group-id", user_group_id);
            },
            update_submit_disabled_state_on_change: true,
        });
    });

    $("#groups_overlay_container").on("click", ".group_settings_header .btn-danger", () => {
        const active_group_data = get_active_data();
        const group_id = active_group_data.id;
        const user_group = user_groups.get_user_group_from_id(group_id);

        if (!user_group || !settings_data.can_edit_user_group(group_id)) {
            return;
        }
        function delete_user_group() {
            channel.del({
                url: "/json/user_groups/" + group_id,
                data: {
                    id: group_id,
                },
                success() {
                    active_group_data.$row.remove();
                },
                error(xhr) {
                    ui_report.error(
                        $t_html({defaultMessage: "Failed"}),
                        xhr,
                        $(".group_change_property_info"),
                    );
                },
            });
        }

        const html_body = render_confirm_delete_user({
            group_name: user_group.name,
        });

        const user_group_name = user_group.name;

        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Delete {user_group_name}?"}, {user_group_name}),
            html_body,
            on_click: delete_user_group,
        });
    });

    function save_group_info(e) {
        const group = get_user_group_for_target(e.currentTarget);

        const url = `/json/user_groups/${group.id}`;
        const data = {};
        const new_name = $("#change_user_group_name").val().trim();
        const new_description = $("#change_user_group_description").val().trim();

        if (new_name !== group.name) {
            data.name = new_name;
        }
        if (new_description !== group.description) {
            data.description = new_description;
        }

        dialog_widget.submit_api_request(channel.patch, url, data);
    }

    $("#groups_overlay_container").on("click", ".create_user_group_button", (e) => {
        e.preventDefault();
        open_create_user_group();
    });

    $("#groups_overlay_container").on("click", "#user_group_creation_form [data-dismiss]", (e) => {
        e.preventDefault();
        // we want to make sure that the click is not just a simulated
        // click; this fixes an issue where hitting "Enter" would
        // trigger this code path due to bootstrap magic.
        if (e.clientY !== 0) {
            open_right_panel_empty();
        }
    });

    $("#groups_overlay_container").on("click", ".group-row", show_right_section);

    $("#groups_overlay_container").on("click", ".fa-chevron-left", () => {
        $(".right").removeClass("show");
        $(".user-groups-header").removeClass("slide-left");
    });

    $("#groups_overlay_container").on("click", ".join_leave_button", (e) => {
        if ($(e.currentTarget).hasClass("disabled")) {
            // We return early if user is not allowed to join or leave a group.
            return;
        }

        const user_group_id = get_user_group_id(e.target);
        const user_group = user_groups.get_user_group_from_id(user_group_id);
        const $group_row = row_for_group_id(user_group_id);
        add_or_remove_from_group(user_group, $group_row);
    });

    $("#groups_overlay_container").on(
        "click",
        ".subsection-header .subsection-changes-save button",
        (e) => {
            e.preventDefault();
            e.stopPropagation();
            const $save_button = $(e.currentTarget);
            const $subsection_elem = $save_button.closest(".settings-subsection-parent");

            const group_id = $save_button.closest(".user_group_settings_wrapper").data("group-id");
            const group = user_groups.get_user_group_from_id(group_id);
            const data = settings_org.populate_data_for_request(
                $subsection_elem,
                false,
                undefined,
                group,
            );

            const url = "/json/user_groups/" + group_id;
            settings_org.save_organization_settings(data, $save_button, url);
        },
    );

    $("#groups_overlay_container").on(
        "click",
        ".subsection-header .subsection-changes-discard button",
        (e) => {
            e.preventDefault();
            e.stopPropagation();

            const group_id = $(e.target).closest(".user_group_settings_wrapper").data("group-id");
            const group = user_groups.get_user_group_from_id(group_id);

            const $subsection = $(e.target).closest(".settings-subsection-parent");
            for (const elem of settings_components.get_subsection_property_elements($subsection)) {
                settings_org.discard_property_element_changes(elem, false, undefined, group);
            }
            const $save_btn_controls = $(e.target).closest(".save-button-controls");
            settings_components.change_save_button_state($save_btn_controls, "discarded");
        },
    );
}

export function launch(section, left_side_tab, right_side_tab) {
    setup_page(() => {
        overlays.open_overlay({
            name: "group_subscriptions",
            $overlay: $("#groups_overlay"),
            on_close() {
                browser_history.exit_overlay();
            },
        });
        change_state(section, left_side_tab, right_side_tab);
    });
    if (!get_active_data().id) {
        if (section === "new") {
            $("#create_user_group_name").trigger("focus");
        } else {
            $("#search_group_name").trigger("focus");
        }
    }
}
