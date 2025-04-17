import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import {z} from "zod";

import render_confirm_delete_user from "../templates/confirm_dialog/confirm_delete_user.hbs";
import render_confirm_join_group_direct_member from "../templates/confirm_dialog/confirm_join_group_direct_member.hbs";
import render_modal_banner from "../templates/modal_banner/modal_banner.hbs";
import render_group_info_banner from "../templates/modal_banner/user_group_info_banner.hbs";
import render_settings_checkbox from "../templates/settings/settings_checkbox.hbs";
import render_browse_user_groups_list_item from "../templates/user_group_settings/browse_user_groups_list_item.hbs";
import render_cannot_deactivate_group_banner from "../templates/user_group_settings/cannot_deactivate_group_banner.hbs";
import render_change_user_group_info_modal from "../templates/user_group_settings/change_user_group_info_modal.hbs";
import render_stream_group_permission_settings from "../templates/user_group_settings/stream_group_permission_settings.hbs";
import render_user_group_membership_status from "../templates/user_group_settings/user_group_membership_status.hbs";
import render_user_group_permission_settings from "../templates/user_group_settings/user_group_permission_settings.hbs";
import render_user_group_settings from "../templates/user_group_settings/user_group_settings.hbs";
import render_user_group_settings_empty_notice from "../templates/user_group_settings/user_group_settings_empty_notice.hbs";
import render_user_group_settings_overlay from "../templates/user_group_settings/user_group_settings_overlay.hbs";

import * as blueslip from "./blueslip.ts";
import * as browser_history from "./browser_history.ts";
import * as channel from "./channel.ts";
import * as components from "./components.ts";
import type {Toggle} from "./components.ts";
import * as compose_banner from "./compose_banner.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import * as group_permission_settings from "./group_permission_settings.ts";
import type {
    GroupGroupSettingName,
    RealmGroupSettingName,
    StreamGroupSettingName,
} from "./group_permission_settings.ts";
import * as hash_util from "./hash_util.ts";
import {$t, $t_html} from "./i18n.ts";
import * as ListWidget from "./list_widget.ts";
import * as loading from "./loading.ts";
import * as overlays from "./overlays.ts";
import * as people from "./people.ts";
import * as resize from "./resize.ts";
import * as scroll_util from "./scroll_util.ts";
import type {UserGroupUpdateEvent} from "./server_event_types.ts";
import * as settings_components from "./settings_components.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as settings_org from "./settings_org.ts";
import {current_user, realm, realm_schema} from "./state_data.ts";
import type {GroupSettingValue} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as timerender from "./timerender.ts";
import {anonymous_group_schema, group_setting_value_schema} from "./types.ts";
import * as ui_report from "./ui_report.ts";
import * as user_group_components from "./user_group_components.ts";
import * as user_group_create from "./user_group_create.ts";
import * as user_group_edit_members from "./user_group_edit_members.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";
import * as user_profile from "./user_profile.ts";
import * as util from "./util.ts";
import * as views_util from "./views_util.ts";

type ActiveData = {
    $row: JQuery | undefined;
    id: number | undefined;
    $tabs: JQuery;
};

let filters_dropdown_widget: dropdown_widget.DropdownWidget;
export const FILTERS = {
    ACTIVE_AND_DEACTIVATED_GROUPS: $t({defaultMessage: "Active and deactivated"}),
    ACTIVE_GROUPS: $t({defaultMessage: "Active groups"}),
    DEACTIVATED_GROUPS: $t({defaultMessage: "Deactivated groups"}),
};
export let toggler: Toggle;
export let select_tab = "general";
const initial_group_filter = FILTERS.ACTIVE_GROUPS;

let group_list_widget: ListWidget.ListWidget<UserGroup, UserGroup>;
let group_list_toggler: Toggle;

function get_user_group_id(target: HTMLElement): number {
    const $row = $(target).closest(
        ".group-row, .user_group_settings_wrapper, .save-button, .group_settings_header",
    );
    return Number.parseInt($row.attr("data-group-id")!, 10);
}

function get_user_group_for_target(target: HTMLElement): UserGroup | undefined {
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

export function get_edit_container(group: UserGroup): JQuery {
    return $(
        `#groups_overlay .user_group_settings_wrapper[data-group-id='${CSS.escape(group.id.toString())}']`,
    );
}

function update_add_members_elements(group: UserGroup): void {
    if (!is_editing_group(group.id)) {
        return;
    }

    // We are only concerned with the Members tab for editing groups.
    const $add_members_container = $<tippy.PopperElement>(
        ".edit_members_for_user_group .add_members_container",
    );

    if (current_user.is_guest || realm.realm_is_zephyr_mirror_realm) {
        // For guest users, we just hide the add_members feature.
        $add_members_container.hide();
        return;
    }

    // Otherwise, we adjust whether the widgets are disabled based on
    // whether this user is authorized to add members.
    const $input_element = $add_members_container.find(".input").expectOne();
    const $button_element = $add_members_container.find("#add_member").expectOne();

    if (settings_data.can_add_members_to_user_group(group.id)) {
        $input_element.prop("contenteditable", true);
        if (user_group_edit_members.pill_widget.items().length > 0) {
            $button_element.prop("disabled", false);
        }
        $button_element.css("pointer-events", "");
        $add_members_container[0]?._tippy?.destroy();
        $add_members_container.removeClass("add_members_disabled");
    } else {
        $input_element.prop("contenteditable", false);
        $button_element.prop("disabled", true);
        $add_members_container.addClass("add_members_disabled");

        const disable_hint = group.deactivated
            ? $t({defaultMessage: "Can't add members to a deactivated group"})
            : $t({defaultMessage: "You are not allowed to add members to this group"});
        settings_components.initialize_disable_button_hint_popover(
            $add_members_container,
            disable_hint,
        );
    }
}

function update_group_permission_settings_elements(group: UserGroup): void {
    if (!is_editing_group(group.id)) {
        return;
    }

    // We are concerned with the General tab for changing group permissions.
    const $group_permission_settings = $("#group_permission_settings");

    const $permission_pill_container_elements = $group_permission_settings.find(".pill-container");
    const $permission_input_groups = $group_permission_settings.find(".input-group");

    if (settings_data.can_manage_user_group(group.id)) {
        $permission_pill_container_elements.find(".input").prop("contenteditable", true);
        $permission_input_groups.removeClass("group_setting_disabled");

        $permission_input_groups.each(function (this: tippy.ReferenceElement) {
            $(this)[0]?._tippy?.destroy();
        });
        settings_components.enable_opening_typeahead_on_clicking_label($group_permission_settings);
    } else {
        $permission_input_groups.each(function () {
            settings_components.initialize_disable_button_hint_popover(
                $(this),
                $t({defaultMessage: "You do not have permission to edit this setting."}),
            );
        });
        settings_components.disable_group_permission_setting($permission_input_groups);
    }
}

function show_membership_settings(group: UserGroup): void {
    const $edit_container = get_edit_container(group);

    const $member_container = $edit_container.find(".edit_members_for_user_group");
    user_group_edit_members.enable_member_management({
        group,
        $parent_container: $member_container,
    });

    update_members_panel_ui(group);
}

function show_general_settings(group: UserGroup): void {
    const permission_settings = group_permission_settings.get_group_permission_settings();
    for (const setting_name of permission_settings) {
        settings_components.create_group_setting_widget({
            $pill_container: $(`#id_${CSS.escape(setting_name)}`),
            setting_name,
            group,
        });
    }

    update_general_panel_ui(group);
}

function update_general_panel_ui(group: UserGroup): void {
    const $edit_container = get_edit_container(group);

    if (settings_data.can_manage_user_group(group.id)) {
        $edit_container.find(".group-header .button-group").show();
        $(
            `.group_settings_header[data-group-id='${CSS.escape(group.id.toString())}'] .deactivate`,
        ).show();
    } else {
        $edit_container.find(".group-header .button-group").hide();
        $(
            `.group_settings_header[data-group-id='${CSS.escape(group.id.toString())}'] .deactivate`,
        ).hide();
    }
    update_group_permission_settings_elements(group);
    update_group_membership_button(group.id);
}

function update_members_panel_ui(group: UserGroup): void {
    const $edit_container = get_edit_container(group);
    const $member_container = $edit_container.find(".edit_members_for_user_group");

    user_group_edit_members.rerender_members_list({
        group,
        $parent_container: $member_container,
    });
    update_add_members_elements(group);
}

export function update_group_management_ui(): void {
    if (!overlays.groups_open()) {
        return;
    }

    const active_group_id = get_active_data().id;

    if (active_group_id === undefined) {
        return;
    }

    const group = user_groups.get_user_group_from_id(active_group_id);

    update_general_panel_ui(group);
    update_members_panel_ui(group);
}

function group_membership_button(group_id: number): JQuery {
    return $(
        `.group_settings_header[data-group-id='${CSS.escape(group_id.toString())}'] .join_leave_button`,
    );
}

function initialize_tooltip_for_membership_button(group_id: number): void {
    const $tooltip_wrapper = group_membership_button(group_id).closest(
        ".join_leave_button_wrapper",
    );
    const is_member = user_groups.is_user_in_group(group_id, people.my_current_user_id());
    const is_deactivated = user_groups.get_user_group_from_id(group_id).deactivated;
    let tooltip_message;
    if (is_deactivated && is_member) {
        tooltip_message = $t({defaultMessage: "You cannot leave a deactivated user group."});
    } else if (is_deactivated) {
        tooltip_message = $t({defaultMessage: "You cannot join a deactivated user group."});
    } else if (is_member) {
        tooltip_message = $t({defaultMessage: "You do not have permission to leave this group."});
    } else {
        tooltip_message = $t({defaultMessage: "You do not have permission to join this group."});
    }
    settings_components.initialize_disable_button_hint_popover($tooltip_wrapper, tooltip_message);
}

// Group membership button only adds or removes direct membership.
function update_group_membership_button(group_id: number): void {
    const $group_settings_button = group_membership_button(group_id);

    if ($group_settings_button.length === 0) {
        return;
    }

    const is_direct_member = user_groups.is_user_in_group(
        group_id,
        people.my_current_user_id(),
        true,
    );
    if (is_direct_member) {
        $group_settings_button.text($t({defaultMessage: "Leave group"}));
    } else {
        $group_settings_button.text($t({defaultMessage: "Join group"}));
    }

    const can_join_group = settings_data.can_join_user_group(group_id);
    const can_leave_group = settings_data.can_leave_user_group(group_id);

    let can_update_membership = true;
    if (!is_direct_member && !can_join_group) {
        can_update_membership = false;
    } else if (is_direct_member && !can_leave_group) {
        can_update_membership = false;
    }

    if (can_update_membership) {
        $group_settings_button.prop("disabled", false);
        $group_settings_button.css("pointer-events", "");
        const $group_settings_button_wrapper: JQuery<tippy.ReferenceElement> =
            $group_settings_button.closest(".join_leave_button_wrapper");
        $group_settings_button_wrapper[0]?._tippy?.destroy();
    } else {
        $group_settings_button.prop("disabled", true);
        initialize_tooltip_for_membership_button(group_id);
    }
}

function rerender_group_row(group: UserGroup): void {
    const $row = row_for_group_id(group.id);

    const item = group;

    const current_user_id = people.my_current_user_id();
    const is_member = user_groups.is_user_in_group(group.id, current_user_id);
    const can_join = settings_data.can_join_user_group(item.id);
    const can_leave = settings_data.can_leave_user_group(item.id);
    const is_direct_member = user_groups.is_direct_member_of(current_user_id, item.id);
    const associated_subgroups = user_groups.get_associated_subgroups(item, current_user_id);
    const associated_subgroup_names = user_groups.format_group_list(associated_subgroups);
    const item_render_data = {
        ...item,
        is_member,
        can_join,
        can_leave,
        is_direct_member,
        associated_subgroup_names,
    };
    const html = render_browse_user_groups_list_item(item_render_data);
    const $new_row = $(html);

    // TODO: Remove this if/when we just handle "active" when rendering templates.
    if ($row.hasClass("active")) {
        $new_row.addClass("active");
    }

    $row.replaceWith($new_row);
}

function update_display_checkmark_on_group_edit(group: UserGroup): void {
    const tab_key = get_active_data().$tabs.first().attr("data-tab-key");
    if (tab_key === "your-groups") {
        // There is no need to do anything if "Your groups" tab is
        // opened, because the whole list is already redrawn.
        return;
    }

    rerender_group_row(group);

    const current_user_id = people.my_current_user_id();
    const supergroups_of_group = user_groups.get_supergroups_of_user_group(group.id);
    for (const supergroup of supergroups_of_group) {
        if (user_groups.is_direct_member_of(current_user_id, supergroup.id)) {
            continue;
        }

        rerender_group_row(supergroup);
    }
}

function update_your_groups_list_if_needed(): void {
    // update display of group-rows on left panel.
    // We need this update only if your-groups tab is active
    // and current user is among the affect users as in that
    // case the group widget list need to be updated and show
    // or remove the group-row on the left panel accordingly.
    const tab_key = get_active_data().$tabs.first().attr("data-tab-key");
    if (tab_key === "your-groups") {
        // We add the group row to list if the current user
        // is added to it. The whole list is redrawed to
        // maintain the sorted order of groups.
        //
        // When the current user is removed from a group, the
        // whole list is redrawn because this action can also
        // affect the memberships of groups that have the
        // updated group as their subgroup.
        redraw_user_group_list();
    }
}

export function handle_subgroup_edit_event(group_id: number, direct_subgroup_ids: number[]): void {
    if (!overlays.groups_open()) {
        return;
    }
    const group = user_groups.get_user_group_from_id(group_id);

    const active_group_id = get_active_data().id;
    const current_user_id = people.my_current_user_id();

    const current_user_in_any_subgroup = user_groups.is_user_in_any_group(
        direct_subgroup_ids,
        current_user_id,
    );

    // update members list if currently rendered.
    if (group_id === active_group_id) {
        user_group_edit_members.update_member_list_widget(group);

        if (
            !user_groups.is_direct_member_of(current_user_id, group_id) &&
            current_user_in_any_subgroup
        ) {
            update_membership_status_text(group);
        }
    } else if (
        active_group_id !== undefined &&
        !user_groups.is_direct_member_of(current_user_id, active_group_id) &&
        user_groups.is_subgroup_of_target_group(active_group_id, group_id)
    ) {
        // Membership status text could still need an update
        // if updated group is one of the subgroup of the group
        // currently opened in right panel.
        const active_group = user_groups.get_user_group_from_id(active_group_id);
        update_membership_status_text(active_group);
    }

    if (current_user_in_any_subgroup) {
        update_your_groups_list_if_needed();
        update_display_checkmark_on_group_edit(group);
    }
    update_permissions_panel_on_subgroup_update(direct_subgroup_ids);
}

function update_status_text_on_member_update(updated_group: UserGroup): void {
    const active_group_id = get_active_data().id;
    if (active_group_id === undefined) {
        return;
    }

    if (updated_group.id === active_group_id) {
        update_membership_status_text(updated_group);
        return;
    }

    // We might need to update the text if the updated groups is
    // one of the subgroups of the group opened in right panel.
    const current_user_id = people.my_current_user_id();
    if (user_groups.is_direct_member_of(current_user_id, active_group_id)) {
        // Since user is already a direct member of the group opened
        // in right panel, the text shown will remain the same.
        return;
    }

    const is_updated_group_subgroup = user_groups.is_subgroup_of_target_group(
        active_group_id,
        updated_group.id,
    );
    if (!is_updated_group_subgroup) {
        return;
    }

    const active_group = user_groups.get_user_group_from_id(active_group_id);
    update_membership_status_text(active_group);
}

function update_settings_for_group_overlay(group_id: number, user_ids: number[]): void {
    const group = user_groups.get_user_group_from_id(group_id);

    // update members list if currently rendered.
    if (is_editing_group(group_id)) {
        if (user_ids.includes(people.my_current_user_id())) {
            update_group_management_ui();
        } else {
            user_group_edit_members.update_member_list_widget(group);
        }
    }

    if (user_ids.includes(people.my_current_user_id())) {
        update_your_groups_list_if_needed();
        update_display_checkmark_on_group_edit(group);

        // Membership status text can be updated even when user was
        // added to a group which is not opened in the right panel as
        // membership can be impacted if the updated group is a
        // subgroup of the group opened in right panel.
        update_status_text_on_member_update(group);
    }
}

export function handle_member_edit_event(group_id: number, user_ids: number[]): void {
    if (overlays.groups_open()) {
        update_settings_for_group_overlay(group_id, user_ids);
    }
    user_profile.update_user_profile_groups_list_for_users(user_ids);
}

export function update_group_details(group: UserGroup): void {
    const $edit_container = get_edit_container(group);
    $edit_container.find(".group-name").text(user_groups.get_display_group_name(group.name));
    $edit_container.find(".group-description").text(group.description);
}

function update_toggler_for_group_setting(group: UserGroup): void {
    if (!group.deactivated) {
        toggler.enable_tab("permissions");
        toggler.goto(select_tab);
    } else {
        if (select_tab === "permissions") {
            toggler.goto("general");
        } else {
            toggler.goto(select_tab);
        }
        toggler.disable_tab("permissions");
    }
}

function get_membership_status_context(group: UserGroup): {
    is_direct_member: boolean;
    is_member: boolean;
    associated_subgroup_names_html: string | undefined;
} {
    const current_user_id = people.my_current_user_id();
    const is_direct_member = user_groups.is_direct_member_of(current_user_id, group.id);

    let is_member;
    let associated_subgroup_names_html;
    if (is_direct_member) {
        is_member = true;
    } else {
        is_member = user_groups.is_user_in_group(group.id, current_user_id);
        if (is_member) {
            const associated_subgroup_names = user_groups
                .get_associated_subgroups(group, current_user_id)
                .map((subgroup) => user_groups.get_display_group_name(subgroup.name));
            associated_subgroup_names_html = util.format_array_as_list_with_highlighted_elements(
                associated_subgroup_names,
                "long",
                "unit",
            );
        }
    }

    return {
        is_direct_member,
        is_member,
        associated_subgroup_names_html,
    };
}

function update_membership_status_text(group: UserGroup): void {
    const args = get_membership_status_context(group);
    const rendered_membership_status = render_user_group_membership_status(args);
    const $edit_container = get_edit_container(group);
    $edit_container.find(".membership-status").html(rendered_membership_status);
}

function save_discard_widget_handler_for_permissions_panel($subsection: JQuery): void {
    $subsection.find(".subsection-failed-status p").hide();
    $subsection.find(".save-button").show();
    const properties_elements = settings_components.get_subsection_property_elements($subsection);
    const show_change_process_button = properties_elements.some((elem) => !$(elem).prop("checked"));

    const $save_button_controls = $subsection.find(".subsection-header .save-button-controls");
    const button_state = show_change_process_button ? "unsaved" : "discarded";
    settings_components.change_save_button_state($save_button_controls, button_state);
}

function get_request_data_for_removing_group_permission(
    current_value: GroupSettingValue,
    removed_group_id: number,
): string {
    const nobody_group = user_groups.get_user_group_from_name("role:nobody")!;

    if (typeof current_value === "number") {
        return JSON.stringify({
            new: nobody_group.id,
            old: current_value,
        });
    }

    let new_setting_value: GroupSettingValue = {...anonymous_group_schema.parse(current_value)};
    new_setting_value.direct_subgroups = new_setting_value.direct_subgroups.filter(
        (group_id) => group_id !== removed_group_id,
    );

    if (
        new_setting_value.direct_subgroups.length === 0 &&
        new_setting_value.direct_members.length === 0
    ) {
        new_setting_value = nobody_group.id;
    }
    return JSON.stringify({
        new: new_setting_value,
        old: current_value,
    });
}

function populate_data_for_removing_realm_permissions(
    $subsection: JQuery,
    group: UserGroup,
): Record<string, string> {
    const changed_setting_elems = settings_components
        .get_subsection_property_elements($subsection)
        .filter((elem) => !$(elem).prop("checked"));
    const changed_setting_names = changed_setting_elems.map((elem) => $(elem).attr("name")!);

    const data: Record<string, string> = {};
    for (const setting_name of changed_setting_names) {
        const current_value = realm[realm_schema.keyof().parse("realm_" + setting_name)];
        data[setting_name] = get_request_data_for_removing_group_permission(
            group_setting_value_schema.parse(current_value),
            group.id,
        );
    }

    return data;
}

function populate_data_for_removing_stream_permissions(
    $subsection: JQuery,
    group: UserGroup,
    sub: StreamSubscription,
): Record<string, string> {
    const changed_setting_elems = settings_components
        .get_subsection_property_elements($subsection)
        .filter((elem) => !$(elem).prop("checked"));
    const changed_setting_names = changed_setting_elems.map((elem) => $(elem).attr("name")!);

    const data: Record<string, string> = {};
    for (const setting_name of changed_setting_names) {
        const current_value = sub[sub_store.stream_subscription_schema.keyof().parse(setting_name)];
        data[setting_name] = get_request_data_for_removing_group_permission(
            group_setting_value_schema.parse(current_value),
            group.id,
        );
    }

    return data;
}

function populate_data_for_removing_user_group_permissions(
    $subsection: JQuery,
    group: UserGroup,
    user_group: UserGroup,
): Record<string, string> {
    const changed_setting_elems = settings_components
        .get_subsection_property_elements($subsection)
        .filter((elem) => !$(elem).prop("checked"));
    const changed_setting_names = changed_setting_elems.map((elem) => $(elem).attr("name")!);

    const data: Record<string, string> = {};
    for (const setting_name of changed_setting_names) {
        const current_value = user_group[user_groups.user_group_schema.keyof().parse(setting_name)];
        data[setting_name] = get_request_data_for_removing_group_permission(
            group_setting_value_schema.parse(current_value),
            group.id,
        );
    }

    return data;
}

export function add_assigned_permission_to_permissions_panel(
    setting_name: string,
    $subsection_elem: JQuery,
    subsection_settings: string[],
    rendered_checkbox_html: string,
): void {
    const $setting_elem = $subsection_elem.find(`.prop-element[name="${CSS.escape(setting_name)}"`);
    if ($setting_elem.length > 0) {
        // If there is already a checkbox for that permission, there can
        // still be changes in permission whether the permission can be
        // removed from the panel or not. So, just replace it with the
        // newly rendered checkbox.
        $setting_elem.closest(".input-group").replaceWith($(rendered_checkbox_html));
        return;
    }

    if ($subsection_elem.hasClass("hide")) {
        $subsection_elem.removeClass("hide");
    }

    if ($subsection_elem.closest(".group-permissions-section").hasClass("hide")) {
        $subsection_elem.closest(".group-permissions-section").removeClass("hide");
    }

    if (!$(".group-assigned-permissions .no-permissions-for-group-text").hasClass("hide")) {
        $(".group-assigned-permissions .no-permissions-for-group-text").addClass("hide");
    }

    let insert_position = 0;
    for (const name of subsection_settings) {
        if (name === setting_name) {
            break;
        }
        if ($subsection_elem.find(`.prop-element[name="${CSS.escape(name)}"`).length > 0) {
            insert_position = insert_position + 1;
        }
    }

    if (insert_position === 0) {
        $subsection_elem.find(".subsection-settings").prepend($(rendered_checkbox_html));
    } else if (insert_position === $subsection_elem.find(".input-group").length) {
        $subsection_elem.find(".subsection-settings").append($(rendered_checkbox_html));
    } else {
        const next_setting_elem = $subsection_elem.find(".subsection-settings .input-group")[
            insert_position
        ]!;
        $(rendered_checkbox_html).insertBefore(next_setting_elem);
    }
}

function remove_setting_checkbox_from_permissions_panel($setting_elem: JQuery): void {
    if ($setting_elem.length === 0) {
        return;
    }

    const $subsection = $setting_elem.closest(".settings-subsection-parent");
    $setting_elem.closest(".input-group").remove();

    if ($subsection.find(".input-group").length === 0) {
        $subsection.addClass("hide");
    }

    // Hide the "Organization permissions", "Channel permissions" or
    // "User group permissions", if there are no assigned permissions
    // for that section.
    if ($subsection.closest(".group-permissions-section").find(".input-group").length === 0) {
        $subsection.closest(".group-permissions-section").addClass("hide");
    }

    // Show the text mentioning group has no permissions if required.
    if ($subsection.closest(".group-assigned-permissions").find(".input-group").length === 0) {
        $subsection
            .closest(".group-assigned-permissions")
            .find(".no-permissions-for-group-text")
            .removeClass("hide");
    }
}

export function update_realm_setting_in_permissions_panel(
    setting_name: RealmGroupSettingName,
    new_value: GroupSettingValue,
): void {
    const active_group_id = get_active_data().id;
    if (active_group_id === undefined) {
        return;
    }

    const $setting_elem = $(`#id_group_permission_${CSS.escape(setting_name)}`);
    const can_edit = settings_config.owner_editable_realm_group_permission_settings.has(
        setting_name,
    )
        ? current_user.is_owner
        : current_user.is_admin;

    const assigned_permission_object = group_permission_settings.get_assigned_permission_object(
        new_value,
        setting_name,
        active_group_id,
        can_edit,
        "realm",
    );

    const group_has_permission = assigned_permission_object !== undefined;

    if (!group_has_permission) {
        remove_setting_checkbox_from_permissions_panel($setting_elem);
        return;
    }

    const subsection_obj = settings_config.realm_group_permission_settings.find((subsection) =>
        subsection.settings.includes(setting_name),
    )!;
    const subsection_settings = subsection_obj.settings;
    const $subsection_elem = $(`.${CSS.escape(subsection_obj.subsection_key)}`);

    const new_setting_checkbox_html = render_settings_checkbox({
        setting_name,
        prefix: "id_group_permission_",
        is_checked: true,
        label: settings_config.all_group_setting_labels.realm[setting_name],
        is_disabled: !assigned_permission_object.can_edit,
        tooltip_message: assigned_permission_object.tooltip_message,
    });

    add_assigned_permission_to_permissions_panel(
        setting_name,
        $subsection_elem,
        subsection_settings,
        new_setting_checkbox_html,
    );
}

export function update_stream_setting_in_permissions_panel(
    setting_name: StreamGroupSettingName,
    new_value: GroupSettingValue,
    sub: StreamSubscription,
): void {
    const active_group_id = get_active_data().id;
    if (active_group_id === undefined) {
        return;
    }

    const $setting_elem = $(
        `#id_group_permission_${CSS.escape(sub.stream_id.toString())}_${CSS.escape(setting_name)}`,
    );

    let can_edit = stream_data.can_change_permissions_requiring_metadata_access(sub);
    if (
        settings_config.stream_group_permission_settings_requiring_content_access.includes(
            setting_name,
        )
    ) {
        can_edit = stream_data.can_change_permissions_requiring_content_access(sub);
    }

    const assigned_permission_object = group_permission_settings.get_assigned_permission_object(
        new_value,
        setting_name,
        active_group_id,
        can_edit,
        "stream",
    );

    const group_has_permission = assigned_permission_object !== undefined;

    if (!group_has_permission) {
        remove_setting_checkbox_from_permissions_panel($setting_elem);
        return;
    }

    const subsection_settings = settings_config.stream_group_permission_settings;
    const $subsection_elem = $(
        `.settings-subsection-parent[data-stream-id="${CSS.escape(sub.stream_id.toString())}"]`,
    );
    const setting_id_prefix = "id_group_permission_" + sub.stream_id.toString() + "_";

    if ($subsection_elem.length === 0) {
        const rendered_subsection_html = render_stream_group_permission_settings({
            stream: sub,
            setting_labels: settings_config.all_group_setting_labels.stream,
            id_prefix: setting_id_prefix,
            assigned_permissions: [
                {
                    setting_name,
                    can_edit: assigned_permission_object.can_edit,
                    tooltip_message: assigned_permission_object.tooltip_message,
                },
            ],
        });

        if ($(".channel-group-permissions").hasClass("hide")) {
            $(".channel-group-permissions").removeClass("hide");
        }

        if (!$(".group-assigned-permissions .no-permissions-for-group-text").hasClass("hide")) {
            $(".group-assigned-permissions .no-permissions-for-group-text").addClass("hide");
        }

        $(".channel-group-permissions").append($(rendered_subsection_html));
        return;
    }

    const rendered_checkbox_html = render_settings_checkbox({
        setting_name,
        prefix: setting_id_prefix,
        is_checked: true,
        label: settings_config.all_group_setting_labels.stream[setting_name],
        is_disabled: !assigned_permission_object.can_edit,
        tooltip_message: assigned_permission_object.tooltip_message,
    });

    add_assigned_permission_to_permissions_panel(
        setting_name,
        $subsection_elem,
        subsection_settings,
        rendered_checkbox_html,
    );
}

export function update_group_setting_in_permissions_panel(
    setting_name: GroupGroupSettingName,
    new_value: GroupSettingValue,
    group: UserGroup,
): void {
    const active_group_id = get_active_data().id;
    if (active_group_id === undefined) {
        return;
    }

    const $setting_elem = $(
        `#id_group_permission_${CSS.escape(group.id.toString())}_${CSS.escape(setting_name)}`,
    );
    const can_edit = settings_data.can_manage_user_group(group.id);

    const assigned_permission_object = group_permission_settings.get_assigned_permission_object(
        new_value,
        setting_name,
        active_group_id,
        can_edit,
        "group",
    );

    const group_has_permission = assigned_permission_object !== undefined;

    if (!group_has_permission) {
        remove_setting_checkbox_from_permissions_panel($setting_elem);
        return;
    }

    const subsection_settings = settings_config.group_permission_settings;
    const $subsection_elem = $(
        `.settings-subsection-parent[data-group-id="${CSS.escape(group.id.toString())}"]`,
    );

    const setting_id_prefix = "id_group_permission_" + group.id.toString() + "_";

    if ($subsection_elem.length === 0) {
        const rendered_subsection_html = render_user_group_permission_settings({
            group_name: user_groups.get_display_group_name(group.name),
            group_id: group.id,
            setting_labels: settings_config.all_group_setting_labels.group,
            id_prefix: setting_id_prefix,
            assigned_permissions: [
                {
                    setting_name,
                    can_edit: assigned_permission_object.can_edit,
                    tooltip_message: assigned_permission_object.tooltip_message,
                },
            ],
        });

        if ($(".user-group-permissions").hasClass("hide")) {
            $(".user-group-permissions").removeClass("hide");
        }

        if (!$(".group-assigned-permissions .no-permissions-for-group-text").hasClass("hide")) {
            $(".group-assigned-permissions .no-permissions-for-group-text").addClass("hide");
        }

        $(".user-group-permissions").append($(rendered_subsection_html));
        return;
    }

    const rendered_checkbox_html = render_settings_checkbox({
        setting_name,
        prefix: setting_id_prefix,
        is_checked: true,
        label: settings_config.all_group_setting_labels.group[setting_name],
        is_disabled: !assigned_permission_object.can_edit,
        tooltip_message: assigned_permission_object.tooltip_message,
    });

    add_assigned_permission_to_permissions_panel(
        setting_name,
        $subsection_elem,
        subsection_settings,
        rendered_checkbox_html,
    );
}

export function show_settings_for(group: UserGroup): void {
    const group_assigned_realm_permissions =
        settings_components.get_group_assigned_realm_permissions(group);
    const group_has_no_realm_permissions = group_assigned_realm_permissions.every(
        (subsection_obj) => subsection_obj.assigned_permissions.length === 0,
    );
    const group_assigned_stream_permissions =
        settings_components.get_group_assigned_stream_permissions(group);
    const group_assigned_user_group_permissions =
        settings_components.get_group_assigned_user_group_permissions(group);

    const html = render_user_group_settings({
        group,
        group_name: user_groups.get_display_group_name(group.name),
        date_created_string: timerender.get_localized_date_or_time_for_format(
            // We get timestamp in seconds from the API but timerender
            // needs milliseconds.
            //
            // Note that the 0 value will never be used in practice,
            // because group.date_created is undefined precisely when
            // group.creator_id is unset.
            new Date((group.date_created ?? 0) * 1000),
            "dayofyear_year",
        ),
        creator: stream_data.maybe_get_creator_details(group.creator_id),
        is_creator: group.creator_id === current_user.user_id,
        ...get_membership_status_context(group),
        all_group_setting_labels: settings_config.all_group_setting_labels,
        group_assigned_realm_permissions,
        group_has_no_realm_permissions,
        group_assigned_stream_permissions,
        group_assigned_user_group_permissions,
        group_has_no_permissions:
            group_has_no_realm_permissions &&
            group_assigned_stream_permissions.length === 0 &&
            group_assigned_user_group_permissions.length === 0,
    });

    scroll_util.get_content_element($("#user_group_settings")).html(html);
    update_toggler_for_group_setting(group);

    toggler.get().prependTo("#user_group_settings .tab-container");
    const $edit_container = get_edit_container(group);
    $(".nothing-selected").hide();

    $edit_container.show();
    show_membership_settings(group);
    show_general_settings(group);

    const context = {
        banner_type: compose_banner.WARNING,
        classname: "group_deactivated",
        hide_close_button: true,
        banner_text: $t({
            defaultMessage:
                "This group is deactivated. It can't be mentioned or used for any permissions.",
        }),
    };

    if (group.deactivated) {
        $("#user_group_settings .group-banner").html(render_modal_banner(context));
    }

    $edit_container
        .find(".group-assigned-permissions")
        .on("change", "input", function (this: HTMLElement, e) {
            e.preventDefault();
            e.stopPropagation();

            const $subsection = $(this).closest(".settings-subsection-parent");
            save_discard_widget_handler_for_permissions_panel($subsection);

            return undefined;
        });

    $edit_container
        .find(".group-assigned-permissions")
        .on(
            "click",
            ".subsection-header .subsection-changes-discard button",
            function (this: HTMLElement, e) {
                e.preventDefault();
                e.stopPropagation();
                const $subsection = $(this).closest(".settings-subsection-parent");
                $subsection.find(".prop-element").prop("checked", true);

                const $save_button_controls = $subsection.find(
                    ".subsection-header .save-button-controls",
                );
                settings_components.change_save_button_state($save_button_controls, "discarded");
            },
        );

    $edit_container
        .find(".realm-group-permissions")
        .on(
            "click",
            ".subsection-header .subsection-changes-save .save-button[data-status='unsaved']",
            function (this: HTMLElement, e: JQuery.ClickEvent) {
                e.preventDefault();
                e.stopPropagation();
                const $save_button = $(this);
                const $subsection_elem = $save_button.closest(".settings-subsection-parent");
                const data = populate_data_for_removing_realm_permissions($subsection_elem, group);
                settings_org.save_organization_settings(data, $save_button, "/json/realm");
            },
        );

    $edit_container
        .find(".channel-group-permissions")
        .on(
            "click",
            ".subsection-header .subsection-changes-save .save-button[data-status='unsaved']",
            function (this: HTMLElement, e: JQuery.ClickEvent) {
                e.preventDefault();
                e.stopPropagation();
                const $save_button = $(this);
                const $subsection_elem = $save_button.closest(".settings-subsection-parent");
                const stream_id = Number.parseInt($subsection_elem.attr("data-stream-id")!, 10);
                const sub = sub_store.get(stream_id)!;
                const data = populate_data_for_removing_stream_permissions(
                    $subsection_elem,
                    group,
                    sub,
                );
                const url = "/json/streams/" + stream_id;
                settings_org.save_organization_settings(data, $save_button, url);
            },
        );

    $edit_container
        .find(".user-group-permissions")
        .on(
            "click",
            ".subsection-header .subsection-changes-save .save-button[data-status='unsaved']",
            function (this: HTMLElement, e: JQuery.ClickEvent) {
                e.preventDefault();
                e.stopPropagation();
                const $save_button = $(this);
                const $subsection_elem = $save_button.closest(".settings-subsection-parent");
                const group_id = Number.parseInt($subsection_elem.attr("data-group-id")!, 10);
                const user_group = user_groups.get_user_group_from_id(group_id);
                const data = populate_data_for_removing_user_group_permissions(
                    $subsection_elem,
                    group,
                    user_group,
                );
                const url = "/json/user_groups/" + group_id;
                settings_org.save_organization_settings(data, $save_button, url);
            },
        );
}

export function setup_group_settings(group: UserGroup): void {
    toggler = components.toggle({
        child_wants_focus: true,
        values: [
            {label: $t({defaultMessage: "General"}), key: "general"},
            {label: $t({defaultMessage: "Members"}), key: "members"},
            {label: $t({defaultMessage: "Permissions"}), key: "permissions"},
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

export function setup_group_list_tab_hash(tab_key_value: string): void {
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

export function update_permissions_panel_on_subgroup_update(subgroup_ids: number[]): void {
    const active_group_id = get_active_data().id;
    if (active_group_id === undefined) {
        return;
    }

    for (const subgroup_id of subgroup_ids) {
        if (
            active_group_id === subgroup_id ||
            // If one of the supergroup of the currently opened group
            // is added/removed from it's supergroup, we need to update
            // the permissions panel.
            user_groups.is_subgroup_of_target_group(subgroup_id, active_group_id)
        ) {
            const group = user_groups.get_user_group_from_id(active_group_id);
            // We can probably write some logic where we don't need to
            // calculate everything again on such change, but this
            // change should not be too frequent in nature and this
            // approach keeps things simple.
            show_settings_for(group);
            return;
        }
    }
    return;
}

function display_membership_toggle_spinner($group_row: JQuery): void {
    /* Prevent sending multiple requests by removing the button class. */
    $group_row.find(".check").removeClass("join_leave_button");

    /* Hide the tick. */
    const $tick = $group_row.find("svg");
    $tick.addClass("hide");

    /* Add a spinner to show the request is in process. */
    const $spinner = $group_row.find(".join_leave_status").expectOne();
    $spinner.show();
    loading.make_indicator($spinner);
}

function hide_membership_toggle_spinner($group_row: JQuery): void {
    /* Re-enable the button to handle requests. */
    $group_row.find(".check").addClass("join_leave_button");

    /* Show the tick. */
    const $tick = $group_row.find("svg");
    $tick.removeClass("hide");

    /* Destroy the spinner. */
    const $spinner = $group_row.find(".join_leave_status").expectOne();
    loading.destroy_indicator($spinner);
}

function empty_right_panel(): void {
    $(".group-row.active").removeClass("active");
    user_group_components.show_user_group_settings_pane.nothing_selected();
}

function open_right_panel_empty(): void {
    empty_right_panel();
    const tab_key = $("#groups_overlay .two-pane-settings-container")
        .find("div.ind-tab.selected")
        .first()
        .attr("data-tab-key");
    assert(tab_key !== undefined);
    setup_group_list_tab_hash(tab_key);
}

export function is_editing_group(desired_group_id: number): boolean {
    if (!overlays.groups_open()) {
        return false;
    }
    return get_active_data().id === desired_group_id;
}

export function handle_deleted_group(group_id: number): void {
    if (!overlays.groups_open()) {
        return;
    }

    if (is_editing_group(group_id)) {
        $("#groups_overlay .deactivated-user-group-icon-right").show();
    }
    redraw_user_group_list();
}

export function show_group_settings(group: UserGroup): void {
    $(".group-row.active").removeClass("active");
    user_group_components.show_user_group_settings_pane.settings(group);
    row_for_group_id(group.id).addClass("active");
    setup_group_settings(group);
}

export function open_group_edit_panel_for_row(group_row: HTMLElement): void {
    const group = get_user_group_for_target(group_row);
    if (group === undefined) {
        return;
    }
    show_group_settings(group);
}

export function set_up_click_handlers(): void {
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

function create_user_group_clicked(): void {
    // this changes the tab switcher (settings/preview) which isn't necessary
    // to a add new stream title.
    user_group_components.show_user_group_settings_pane.create_user_group();
    $(".group-row.active").removeClass("active");

    user_group_create.show_new_user_group_modal();
    $("#create_user_group_name").trigger("focus");
}

export function do_open_create_user_group(): void {
    // Only call this directly for hash changes.
    // Prefer open_create_user_group().
    show_right_section();
    create_user_group_clicked();
}

export function open_create_user_group(): void {
    do_open_create_user_group();
    browser_history.update("#groups/new");
}

export function row_for_group_id(group_id: number): JQuery {
    return $(`.group-row[data-group-id='${CSS.escape(group_id.toString())}']`);
}

export function is_group_already_present(group: UserGroup): boolean {
    return row_for_group_id(group.id).length > 0;
}

export function get_active_data(): ActiveData {
    const $active_tabs = $("#groups_overlay .two-pane-settings-container").find(
        "div.ind-tab.selected",
    );
    const active_group_id = user_group_components.active_group_id;
    let $row;
    if (active_group_id !== undefined) {
        $row = row_for_group_id(active_group_id);
    }
    return {
        $row,
        id: user_group_components.active_group_id,
        $tabs: $active_tabs,
    };
}

export function switch_to_group_row(group: UserGroup): void {
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

        get_active_data().$row?.removeClass("active");
        $group_row.addClass("active");

        scroll_util.scroll_element_into_container($group_row, $container);
    }

    show_group_settings(group);
}

function show_right_section(): void {
    $(".right").addClass("show");
    $("#groups_overlay .two-pane-settings-header").addClass("slide-left");
}

export function add_group_to_table(group: UserGroup): void {
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

export function sync_group_permission_setting(property: string, group: UserGroup): void {
    const $elem = $(`#id_${CSS.escape(property)}`);
    const $subsection = $elem.closest(".settings-subsection-parent");
    if ($subsection.find(".save-button-controls").hasClass("hide")) {
        settings_org.discard_group_property_element_changes($elem, group);
    } else {
        settings_org.discard_group_settings_subsection_changes($subsection, group);
    }
}

export function update_group_right_panel(group: UserGroup, changed_settings: string[]): void {
    if (changed_settings.includes("can_manage_group")) {
        update_group_management_ui();
        return;
    }

    if (
        changed_settings.includes("can_add_members_group") ||
        changed_settings.includes("can_remove_members_group")
    ) {
        update_group_membership_button(group.id);
        update_members_panel_ui(group);
        return;
    }

    if (
        changed_settings.includes("can_join_group") ||
        changed_settings.includes("can_leave_group")
    ) {
        update_group_membership_button(group.id);
        return;
    }
}

export function update_group(event: UserGroupUpdateEvent, group: UserGroup): void {
    if (!overlays.groups_open()) {
        return;
    }

    // update left side pane
    const $group_row = row_for_group_id(group.id);
    if (event.data.name !== undefined) {
        $group_row.find(".group-name").text(user_groups.get_display_group_name(group.name));
        user_group_create.maybe_update_error_message();
    }

    if (event.data.description !== undefined) {
        $group_row.find(".description").text(group.description);
    }

    if (event.data.deactivated) {
        $("#user-group-edit-filter-options").show();
        handle_deleted_group(group.id);
        return;
    }

    const changed_group_settings = group_permission_settings
        .get_group_permission_settings()
        .filter((setting_name) => event.data[setting_name] !== undefined);

    if (get_active_data().id === group.id) {
        // update right side pane
        update_group_details(group);
        if (event.data.name !== undefined) {
            // update settings title
            $("#groups_overlay .user-group-info-title")
                .text(user_groups.get_display_group_name(group.name))
                .addClass("showing-info-title");
        }

        if (changed_group_settings.length > 0) {
            update_group_right_panel(group, changed_group_settings);
        }
    }

    for (const setting_name of changed_group_settings) {
        if (get_active_data().id === group.id) {
            sync_group_permission_setting(setting_name, group);
        }
        update_group_setting_in_permissions_panel(
            setting_name,
            group_setting_value_schema.parse(event.data[setting_name]),
            group,
        );
    }
}

export function change_state(
    section: string,
    left_side_tab: string | undefined,
    right_side_tab: string,
): void {
    if (section === "new") {
        do_open_create_user_group();
        redraw_user_group_list();
        resize.resize_settings_creation_overlay();
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
        const group_visibility = group.deactivated
            ? FILTERS.DEACTIVATED_GROUPS
            : FILTERS.ACTIVE_GROUPS;

        update_displayed_groups(group_visibility);
        if (filters_dropdown_widget) {
            filters_dropdown_widget.render(group_visibility);
        }
        show_right_section();
        select_tab = right_side_tab;

        if (left_side_tab === undefined) {
            left_side_tab = "all-groups";
            if (user_groups.is_user_in_group(group_id, current_user.user_id)) {
                left_side_tab = "your-groups";
            }
        }

        // Callback to .goto() will update browser_history unless a
        // group is being edited. We are always editing a group here
        // so its safe to call
        if (left_side_tab !== group_list_toggler.value()) {
            user_group_components.set_active_group_id(group.id);
            group_list_toggler.goto(left_side_tab);
        }
        switch_to_group_row(group);
        return;
    }

    group_list_toggler.goto("your-groups");
    empty_right_panel();
}

function compare_by_name(a: UserGroup, b: UserGroup): number {
    return util.strcmp(a.name, b.name);
}

function redraw_left_panel(tab_name: string): void {
    let groups_list_data;
    if (tab_name === "all-groups") {
        groups_list_data = user_groups.get_realm_user_groups(true);
    } else if (tab_name === "your-groups") {
        groups_list_data = user_groups.get_user_groups_of_user(people.my_current_user_id(), true);
    }
    if (groups_list_data === undefined) {
        return;
    }
    groups_list_data.sort(compare_by_name);
    group_list_widget.replace_list_data(groups_list_data);
    update_empty_left_panel_message();
}

export function redraw_user_group_list(): void {
    const tab_name = get_active_data().$tabs.first().attr("data-tab-key");
    assert(tab_name !== undefined);
    redraw_left_panel(tab_name);
}

export function switch_group_tab(tab_name: string): void {
    /*
        This switches the groups list tab, but it doesn't update
        the group_list_toggler widget.  You may instead want to
        use `group_list_toggler.goto`.
    */

    redraw_left_panel(tab_name);
    setup_group_list_tab_hash(tab_name);
}

export function add_or_remove_from_group(group: UserGroup, $group_row: JQuery): void {
    const user_id = people.my_current_user_id();
    function success_callback(): void {
        if ($group_row.length > 0) {
            hide_membership_toggle_spinner($group_row);
            // This should only be triggered when a user is on another group
            // edit panel and they join a group via the left panel plus button.
            // In that case, the edit panel of the newly joined group should
            // open. `is_user_in_group` with direct_members_only set to true acts
            // as a proxy to check if it's an `add_members` event.
            if (
                !is_editing_group(group.id) &&
                user_groups.is_user_in_group(group.id, user_id, true)
            ) {
                open_group_edit_panel_for_row(util.the($group_row));
            }
        }
    }

    function error_callback(): void {
        if ($group_row.length > 0) {
            hide_membership_toggle_spinner($group_row);
        }
    }

    if ($group_row.length > 0) {
        display_membership_toggle_spinner($group_row);
    }
    if (user_groups.is_direct_member_of(user_id, group.id)) {
        user_group_edit_members.edit_user_group_membership({
            group,
            removed: [user_id],
            success: success_callback,
            error: error_callback,
        });
    } else {
        user_group_edit_members.edit_user_group_membership({
            group,
            added: [user_id],
            success: success_callback,
            error: error_callback,
        });
    }
}

export function update_empty_left_panel_message(): void {
    // Check if we have any groups in panel to decide whether to
    // display a notice.
    const is_your_groups_tab_active =
        get_active_data().$tabs.first().attr("data-tab-key") === "your-groups";

    let current_group_filter =
        z.string().optional().parse(filters_dropdown_widget.value()) ??
        FILTERS.ACTIVE_AND_DEACTIVATED_GROUPS;

    // When the dropdown menu is hidden.
    if ($("#user-group-edit-filter-options").is(":hidden")) {
        current_group_filter = FILTERS.ACTIVE_AND_DEACTIVATED_GROUPS;
    }

    if ($(".user-groups-list").find(".group-row:visible").length > 0) {
        $(".no-groups-to-show").hide();
        return;
    }

    const empty_user_group_list_message = get_empty_user_group_list_message(
        current_group_filter,
        is_your_groups_tab_active,
    );

    const args = {
        empty_user_group_list_message,
        can_create_user_groups:
            settings_data.user_can_create_user_groups() && realm.zulip_plan_is_not_limited,
        all_groups_tab: !is_your_groups_tab_active,
    };

    $(".no-groups-to-show").html(render_user_group_settings_empty_notice(args)).show();
}

function get_empty_user_group_list_message(
    current_group_filter: string,
    is_your_groups_tab_active: boolean,
): string {
    const is_searching = $("#search_group_name").val() !== "";
    if (is_searching || current_group_filter !== FILTERS.ACTIVE_AND_DEACTIVATED_GROUPS) {
        return $t({defaultMessage: "There are no groups matching your filters."});
    }

    if (is_your_groups_tab_active) {
        return $t({defaultMessage: "You are not a member of any user groups."});
    }
    return $t({
        defaultMessage: "There are no user groups you can view in this organization.",
    });
}

const throttled_update_empty_left_panel_message = _.throttle(() => {
    update_empty_left_panel_message();
}, 100);

export function remove_deactivated_user_from_all_groups(user_id: number): void {
    const all_user_groups = user_groups.get_realm_user_groups(true);

    for (const user_group of all_user_groups) {
        if (user_groups.is_direct_member_of(user_id, user_group.id)) {
            user_groups.remove_members(user_group.id, [user_id]);
        }

        // update members list if currently rendered.
        if (overlays.groups_open() && is_editing_group(user_group.id)) {
            user_group_edit_members.update_member_list_widget(user_group);
        }
    }
}

export function update_displayed_groups(filter_id: string): void {
    if (filter_id === FILTERS.ACTIVE_GROUPS) {
        $(".user-groups-list").addClass("hide-deactived-user-groups");
        $(".user-groups-list").removeClass("hide-active-user-groups");
    } else if (filter_id === FILTERS.DEACTIVATED_GROUPS) {
        $(".user-groups-list").removeClass("hide-deactived-user-groups");
        $(".user-groups-list").addClass("hide-active-user-groups");
    } else {
        $(".user-groups-list").removeClass("hide-deactived-user-groups");
        $(".user-groups-list").removeClass("hide-active-user-groups");
    }
}

export function filter_click_handler(
    event: JQuery.TriggeredEvent,
    dropdown: tippy.Instance,
    widget: dropdown_widget.DropdownWidget,
): void {
    event.preventDefault();
    event.stopPropagation();
    const filter_id = z.string().parse(widget.value());
    update_displayed_groups(filter_id);
    update_empty_left_panel_message();
    dropdown.hide();
    widget.render();
}

function filters_dropdown_options(
    current_value: string | number | undefined,
): dropdown_widget.Option[] {
    return [
        {
            unique_id: FILTERS.ACTIVE_GROUPS,
            name: FILTERS.ACTIVE_GROUPS,
            bold_current_selection: current_value === FILTERS.ACTIVE_GROUPS,
        },
        {
            unique_id: FILTERS.DEACTIVATED_GROUPS,
            name: FILTERS.DEACTIVATED_GROUPS,
            bold_current_selection: current_value === FILTERS.DEACTIVATED_GROUPS,
        },
        {
            unique_id: FILTERS.ACTIVE_AND_DEACTIVATED_GROUPS,
            name: FILTERS.ACTIVE_AND_DEACTIVATED_GROUPS,
            bold_current_selection: current_value === FILTERS.ACTIVE_AND_DEACTIVATED_GROUPS,
        },
    ];
}

function setup_dropdown_filters_widget(): void {
    filters_dropdown_widget = new dropdown_widget.DropdownWidget({
        ...views_util.COMMON_DROPDOWN_WIDGET_PARAMS,
        get_options: filters_dropdown_options,
        widget_name: "user_group_visibility_settings",
        item_click_callback: filter_click_handler,
        $events_container: $("#user-group-edit-filter-options"),
        default_id: initial_group_filter,
    });
    filters_dropdown_widget.setup();
}

export function setup_page(callback: () => void): void {
    function initialize_components(): void {
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

        if (user_groups.realm_has_deactivated_user_groups()) {
            $("#user-group-edit-filter-options").show();
        } else {
            $("#user-group-edit-filter-options").hide();
        }
        group_list_toggler.get().prependTo("#groups_overlay_container .list-toggler-container");
        setup_dropdown_filters_widget();
    }

    function populate_and_fill(): void {
        const template_data = {
            can_create_user_groups: settings_data.user_can_create_user_groups(),
            zulip_plan_is_not_limited: realm.zulip_plan_is_not_limited,
            upgrade_text_for_wide_organization_logo: realm.upgrade_text_for_wide_organization_logo,
            is_business_type_org:
                realm.realm_org_type === settings_config.all_org_type_values.business.code,
            max_user_group_name_length: user_groups.max_user_group_name_length,
            all_group_setting_labels: settings_config.all_group_setting_labels,
            has_billing_access: settings_data.user_has_billing_access(),
        };

        const groups_overlay_html = render_user_group_settings_overlay(template_data);

        const $groups_overlay_container = scroll_util.get_content_element(
            $("#groups_overlay_container"),
        );
        $groups_overlay_container.html(groups_overlay_html);
        update_displayed_groups(initial_group_filter);
        const context = {
            banner_type: compose_banner.INFO,
            classname: "group_info",
            hide_close_button: true,
            button_text: $t({defaultMessage: "Learn more"}),
            button_link: "/help/user-groups",
        };

        $("#groups_overlay_container .nothing-selected .group-info-banner").html(
            render_group_info_banner(context),
        );

        // Initially as the overlay is build with empty right panel,
        // active_group_id is undefined.
        user_group_components.reset_active_group_id();

        const $container = $("#groups_overlay_container .user-groups-list");

        /*
            As change_state function called after this initial build up
            redraws left panel based on active tab we avoid building extra dom
            here as the required group-rows are anyway going to be created
            immediately after this due to call to change_state. So we call
            `ListWidget.create` with empty user groups list.
        */
        const empty_user_group_list: UserGroup[] = [];
        group_list_widget = ListWidget.create($container, empty_user_group_list, {
            name: "user-groups-overlay",
            get_item: ListWidget.default_get_item,
            modifier_html(item) {
                const is_member = user_groups.is_user_in_group(
                    item.id,
                    people.my_current_user_id(),
                );
                const is_direct_member = user_groups.is_direct_member_of(
                    people.my_current_user_id(),
                    item.id,
                );
                const associated_subgroups = user_groups.get_associated_subgroups(
                    item,
                    people.my_current_user_id(),
                );
                const associated_subgroup_names =
                    user_groups.format_group_list(associated_subgroups);
                const can_join = settings_data.can_join_user_group(item.id);
                const can_leave = settings_data.can_leave_user_group(item.id);
                const item_render_data = {
                    ...item,
                    is_member,
                    is_direct_member,
                    associated_subgroup_names,
                    can_join,
                    can_leave,
                };
                return render_browse_user_groups_list_item(item_render_data);
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
                    // We throttle this to not call this check on every keypress
                    throttled_update_empty_left_panel_message();
                    if (user_group_components.active_group_id !== undefined) {
                        const active_group = user_groups.get_user_group_from_id(
                            user_group_components.active_group_id,
                        );
                        if (is_group_already_present(active_group)) {
                            row_for_group_id(user_group_components.active_group_id).addClass(
                                "active",
                            );
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

export function initialize(): void {
    $("#groups_overlay_container").on("click", ".group-row", function (this: HTMLElement) {
        if ($(this).closest(".check, .user_group_settings_wrapper").length === 0) {
            open_group_edit_panel_for_row(this);
        }
    });

    $("#groups_overlay_container").on(
        "click",
        "#open_group_info_modal",
        function (this: HTMLElement, e) {
            e.preventDefault();
            e.stopPropagation();
            const user_group_id = get_user_group_id(this);
            const user_group = user_groups.get_user_group_from_id(user_group_id);
            const template_data = {
                group_name: user_groups.get_display_group_name(user_group.name),
                group_description: user_group.description,
                max_user_group_name_length: user_groups.max_user_group_name_length,
                allow_editing_description: true,
            };
            const change_user_group_info_modal = render_change_user_group_info_modal(template_data);
            dialog_widget.launch({
                html_heading: $t_html(
                    {defaultMessage: "Edit {group_name}"},
                    {group_name: user_groups.get_display_group_name(user_group.name)},
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
        },
    );

    $("#groups_overlay_container").on(
        "click",
        ".group_settings_header .deactivate-group-button",
        () => {
            const active_group_data = get_active_data();
            const group_id = active_group_data.id;
            assert(group_id !== undefined);
            const user_group = user_groups.get_user_group_from_id(group_id);

            if (!user_group || !settings_data.can_manage_user_group(group_id)) {
                return;
            }
            function deactivate_user_group(): void {
                channel.post({
                    url: "/json/user_groups/" + group_id + "/deactivate",
                    data: {},
                    success() {
                        dialog_widget.close();
                        active_group_data.$row?.remove();
                    },
                    error(xhr) {
                        dialog_widget.hide_dialog_spinner();
                        const parsed = z
                            .object({
                                code: z.string(),
                                msg: z.string(),
                                objections: z.array(z.record(z.string(), z.unknown())),
                                result: z.string(),
                            })
                            .safeParse(xhr.responseJSON);
                        if (
                            parsed.success &&
                            parsed.data.code === "CANNOT_DEACTIVATE_GROUP_IN_USE"
                        ) {
                            $("#deactivation-confirm-modal .dialog_submit_button").prop(
                                "disabled",
                                true,
                            );
                            const rendered_error_banner = render_cannot_deactivate_group_banner();
                            $("#dialog_error")
                                .html(rendered_error_banner)
                                .addClass("alert-error")
                                .show();

                            $("#dialog_error .permissions-button").on("click", () => {
                                select_tab = "permissions";
                                update_toggler_for_group_setting(user_group);
                                dialog_widget.close();
                            });
                        } else {
                            ui_report.error(
                                $t({defaultMessage: "Failed"}),
                                xhr,
                                $("#dialog_error"),
                            );
                        }
                    },
                });
            }

            const group_name = user_groups.get_display_group_name(user_group.name);
            const html_body = render_confirm_delete_user({
                group_name,
            });

            confirm_dialog.launch({
                html_heading: $t_html({defaultMessage: "Deactivate {group_name}?"}, {group_name}),
                html_body,
                on_click: deactivate_user_group,
                close_on_submit: false,
                loading_spinner: true,
                id: "deactivation-confirm-modal",
            });
        },
    );

    function save_group_info(e: JQuery.ClickEvent): void {
        assert(e.currentTarget instanceof HTMLElement);
        const group = get_user_group_for_target(e.currentTarget);
        assert(group !== undefined);
        const url = `/json/user_groups/${group.id}`;
        let name;
        let description;
        const new_name = $<HTMLInputElement>("#change_user_group_name").val()!.trim();
        const new_description = $<HTMLInputElement>("#change_user_group_description").val()!.trim();

        if (new_name !== group.name) {
            name = new_name;
        }
        if (new_description !== group.description) {
            description = new_description;
        }
        const data = {
            name,
            description,
        };
        dialog_widget.submit_api_request(channel.patch, url, data);
    }

    $("#groups_overlay_container").on("click", ".create_user_group_button", (e) => {
        e.preventDefault();
        open_create_user_group();
    });

    $("#groups_overlay_container").on(
        "click",
        "#user_group_creation_form .create_user_group_cancel",
        (e) => {
            e.preventDefault();
            // we want to make sure that the click is not just a simulated
            // click; this fixes an issue where hitting "Enter" would
            // trigger this code path due to bootstrap magic.
            if (e.clientY !== 0) {
                open_right_panel_empty();
            }
        },
    );

    $("#groups_overlay_container").on("click", ".group-row", show_right_section);

    $("#groups_overlay_container").on("click", ".fa-chevron-left", () => {
        $(".right").removeClass("show");
        $("#groups_overlay_container .two-pane-settings-header").removeClass("slide-left");
    });

    $("#groups_overlay_container").on("click", ".join_leave_button", function (this: HTMLElement) {
        if ($(this).hasClass("disabled") || $(this).hasClass("not-direct-member")) {
            // We return early if user is not allowed to join or leave a group.
            return;
        }

        const user_group_id = get_user_group_id(this);
        const user_group = user_groups.get_user_group_from_id(user_group_id);
        const is_member = user_groups.is_user_in_group(user_group_id, people.my_current_user_id());
        const is_direct_member = user_groups.is_direct_member_of(
            people.my_current_user_id(),
            user_group_id,
        );

        if (is_member && !is_direct_member) {
            const associated_subgroups = user_groups.get_associated_subgroups(
                user_group,
                people.my_current_user_id(),
            );
            const associated_subgroup_names = user_groups.format_group_list(associated_subgroups);

            confirm_dialog.launch({
                html_heading: $t_html({defaultMessage: "Join group?"}),
                html_body: render_confirm_join_group_direct_member({
                    associated_subgroup_names,
                }),
                id: "confirm_join_group_direct_member",
                on_click() {
                    const $group_row = row_for_group_id(user_group_id);
                    add_or_remove_from_group(user_group, $group_row);
                },
            });
        } else {
            const $group_row = row_for_group_id(user_group_id);
            add_or_remove_from_group(user_group, $group_row);
        }
    });

    $("#groups_overlay_container").on(
        "click",
        ".subsection-header .subsection-changes-save .save-button[data-status='unsaved']",
        function (this: HTMLElement, e) {
            e.preventDefault();
            e.stopPropagation();
            const $save_button = $(this);
            const $subsection_elem = $save_button.closest(".settings-subsection-parent");

            const group_id: unknown = $save_button
                .closest(".user_group_settings_wrapper")
                .data("group-id");
            assert(typeof group_id === "number");
            const group = user_groups.get_user_group_from_id(group_id);
            const data = settings_components.populate_data_for_group_request(
                $subsection_elem,
                group,
            );

            const url = "/json/user_groups/" + group_id;
            settings_org.save_organization_settings(data, $save_button, url);
        },
    );

    $("#groups_overlay_container").on(
        "click",
        ".subsection-header .subsection-changes-discard button",
        function (this: HTMLElement, e) {
            e.preventDefault();
            e.stopPropagation();

            const group_id: unknown = $(this)
                .closest(".user_group_settings_wrapper")
                .data("group-id");
            assert(typeof group_id === "number");
            const group = user_groups.get_user_group_from_id(group_id);

            const $subsection = $(this).closest(".settings-subsection-parent");
            settings_org.discard_group_settings_subsection_changes($subsection, group);
        },
    );
}

export function launch(
    section: string,
    left_side_tab: string | undefined,
    right_side_tab: string,
): void {
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
