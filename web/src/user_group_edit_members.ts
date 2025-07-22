import Handlebars from "handlebars/runtime.js";
import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_leave_user_group_modal from "../templates/confirm_dialog/confirm_unsubscribe_private_stream.hbs";
import render_user_group_member_list_entry from "../templates/stream_settings/stream_member_list_entry.hbs";
import render_user_group_members_table from "../templates/user_group_settings/user_group_members_table.hbs";
import render_user_group_membership_request_result from "../templates/user_group_settings/user_group_membership_request_result.hbs";
import render_user_group_subgroup_entry from "../templates/user_group_settings/user_group_subgroup_entry.hbs";

import * as add_group_members_pill from "./add_group_members_pill.ts";
import * as blueslip from "./blueslip.ts";
import * as buttons from "./buttons.ts";
import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import {$t, $t_html} from "./i18n.ts";
import * as ListWidget from "./list_widget.ts";
import type {ListWidget as ListWidgetType} from "./list_widget.ts";
import * as people from "./people.ts";
import type {User} from "./people.ts";
import * as scroll_util from "./scroll_util.ts";
import * as settings_data from "./settings_data.ts";
import {current_user} from "./state_data.ts";
import type {CombinedPillContainer} from "./typeahead_helper.ts";
import * as user_group_components from "./user_group_components.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";
import * as util from "./util.ts";

export let pill_widget: CombinedPillContainer;
let current_group_id: number;
let member_list_widget: ListWidgetType<User | UserGroup, User | UserGroup>;

function get_potential_members(): User[] {
    const group = user_groups.get_user_group_from_id(current_group_id);
    function is_potential_member(person: User): boolean {
        // user verbose style filter to have room
        // to add more potential checks easily.
        if (group.members.has(person.user_id)) {
            return false;
        }
        return true;
    }

    return people.filter_all_users(is_potential_member);
}

function get_potential_subgroups(): UserGroup[] {
    return user_groups.get_potential_subgroups(current_group_id);
}

function get_user_group_members(group: UserGroup): (User | UserGroup)[] {
    const member_ids = [...group.members];
    const member_users = people.get_users_from_ids(member_ids);
    people.sort_but_pin_current_user_on_top(member_users);

    const subgroup_ids = [...group.direct_subgroup_ids];
    const subgroups = subgroup_ids
        .map((group_id) => user_groups.get_user_group_from_id(group_id))
        .sort(user_group_components.sort_group_member_name);

    return [...subgroups, ...member_users];
}

export function update_member_list_widget(group: UserGroup): void {
    assert(group.id === current_group_id, "Unexpected group rerendering members list");
    const users = get_user_group_members(group);
    member_list_widget.replace_list_data(users);
}

function format_member_list_elem(person: User): string {
    return render_user_group_member_list_entry({
        name: person.full_name,
        user_id: person.user_id,
        is_current_user: person.user_id === current_user.user_id,
        email: person.delivery_email,
        can_remove_subscribers: settings_data.can_remove_members_from_user_group(current_group_id),
        for_user_group_members: true,
        img_src: people.small_avatar_url_for_person(person),
    });
}

function format_subgroup_list_elem(group: UserGroup): string {
    return render_user_group_subgroup_entry({
        group_id: group.id,
        display_value: user_groups.get_display_group_name(group.name),
        can_remove_members: settings_data.can_remove_members_from_user_group(current_group_id),
    });
}

function make_list_widget({
    $parent_container,
    name,
    users,
}: {
    $parent_container: JQuery;
    name: string;
    users: (User | UserGroup)[];
}): ListWidgetType<User | UserGroup, User | UserGroup> {
    const $list_container = $parent_container.find(".member_table");
    $list_container.empty();

    const $simplebar_container = $parent_container.find(".member_list_container");

    return ListWidget.create($list_container, users, {
        name,
        get_item: ListWidget.default_get_item,
        $parent_container,
        sort_fields: {
            email: user_group_components.sort_group_member_email,
            name: user_group_components.sort_group_member_name,
        },
        modifier_html(item) {
            if ("user_id" in item) {
                return format_member_list_elem(item);
            }
            return format_subgroup_list_elem(item);
        },
        filter: {
            $element: $parent_container.find<HTMLInputElement>("input.search"),
            predicate(person, value) {
                const matcher = user_group_components.build_group_member_matcher(value);
                const match = matcher(person);

                return match;
            },
        },
        $simplebar_container,
    });
}

export function enable_member_management({
    group,
    $parent_container,
}: {
    group: UserGroup;
    $parent_container: JQuery;
}): void {
    const group_id = group.id;

    const $pill_container = $parent_container.find(".pill-container");

    // current_group_id and pill_widget are module-level variables
    current_group_id = group_id;

    pill_widget = add_group_members_pill.create({
        $pill_container,
        get_potential_members,
        get_potential_groups: get_potential_subgroups,
        with_add_button: true,
    });

    $pill_container.find(".input").on("input", () => {
        $parent_container.find(".user_group_subscription_request_result").empty();
    });

    member_list_widget = make_list_widget({
        $parent_container,
        name: "user_group_members",
        users: get_user_group_members(group),
    });
}

export function rerender_members_list({
    group,
    $parent_container,
}: {
    group: UserGroup;
    $parent_container: JQuery;
}): void {
    $parent_container.find(".member-list-box").html(
        render_user_group_members_table({
            can_remove_members: settings_data.can_remove_members_from_user_group(group.id),
        }),
    );
    member_list_widget = make_list_widget({
        $parent_container,
        name: "user_group_members",
        users: get_user_group_members(group),
    });
}

function generate_group_link_html(group: UserGroup): string {
    const group_name = user_groups.get_display_group_name(group.name);
    return `<a data-user-group-id="${group.id}" class="view_user_group">${Handlebars.Utils.escapeExpression(group_name)}</a>`;
}

function generate_user_link_html(user: User): string {
    return `<a data-user-id="${user.user_id}" class="view_user_profile">${Handlebars.Utils.escapeExpression(user.full_name)}</a>`;
}

function generate_members_added_success_messages(
    newly_added_users: User[],
    newly_added_subgroups: UserGroup[],
    already_added_users: User[],
    already_added_subgroups: UserGroup[],
    ignored_deactivated_groups: UserGroup[],
    ignored_deactivated_users: User[],
): {
    newly_added_members_message_html: string;
    already_added_members_message_html: string;
    ignored_deactivated_users_message_html: string;
    ignored_deactivated_groups_message_html: string;
} {
    const new_user_links = newly_added_users.map((user) => generate_user_link_html(user));
    const new_group_links = newly_added_subgroups.map((group) => generate_group_link_html(group));
    const old_user_links = already_added_users.map((user) => generate_user_link_html(user));
    const old_group_links = already_added_subgroups.map((group) => generate_group_link_html(group));
    const ignored_group_links = ignored_deactivated_groups.map((group) =>
        generate_group_link_html(group),
    );
    const ignored_user_links = ignored_deactivated_users.map((user) =>
        generate_user_link_html(user),
    );

    const newly_added_members_message_html = util.format_array_as_list_with_conjunction(
        [...new_user_links, ...new_group_links],
        "long",
    );
    const already_added_members_message_html = util.format_array_as_list_with_conjunction(
        [...old_user_links, ...old_group_links],
        "long",
    );
    const ignored_deactivated_users_message_html = util.format_array_as_list_with_conjunction(
        ignored_user_links,
        "long",
    );
    const ignored_deactivated_groups_message_html = util.format_array_as_list_with_conjunction(
        ignored_group_links,
        "long",
    );
    return {
        newly_added_members_message_html,
        already_added_members_message_html,
        ignored_deactivated_users_message_html,
        ignored_deactivated_groups_message_html,
    };
}

function show_user_group_membership_request_error_result(error_message: string): void {
    const $user_group_subscription_req_result_elem = $(
        ".user_group_subscription_request_result",
    ).expectOne();
    const html = render_user_group_membership_request_result({
        error_message,
    });
    scroll_util.get_content_element($user_group_subscription_req_result_elem).html(html);
}

function show_user_group_membership_request_success_result({
    already_added_users,
    newly_added_users,
    newly_added_subgroups,
    ignored_deactivated_users,
    already_added_subgroups,
    ignored_deactivated_groups,
}: {
    newly_added_users: User[];
    newly_added_subgroups: UserGroup[];
    already_added_users: User[];
    ignored_deactivated_users: User[];
    already_added_subgroups: UserGroup[];
    ignored_deactivated_groups: UserGroup[];
}): void {
    const newly_added_user_count = newly_added_users.length;
    const newly_added_subgroups_count = newly_added_subgroups.length;
    const already_added_user_count = already_added_users.length;
    const already_added_subgroups_count = already_added_subgroups.length;
    const ignored_deactivated_groups_count = ignored_deactivated_groups.length;
    const ignored_deactivated_users_count = ignored_deactivated_users.length;

    const total_member_count_exceeds_five =
        newly_added_user_count +
            newly_added_subgroups_count +
            already_added_user_count +
            already_added_subgroups_count +
            ignored_deactivated_groups_count +
            ignored_deactivated_users_count >
        5;

    const newly_added_member_count = newly_added_user_count + newly_added_subgroups_count;
    const already_added_member_count = already_added_user_count + already_added_subgroups_count;
    const ignored_deactivated_member_count =
        ignored_deactivated_users_count + ignored_deactivated_groups_count;
    let addition_success_messages;
    if (!total_member_count_exceeds_five) {
        addition_success_messages = generate_members_added_success_messages(
            newly_added_users,
            newly_added_subgroups,
            already_added_users,
            already_added_subgroups,
            ignored_deactivated_groups,
            ignored_deactivated_users,
        );
    }

    const $user_group_subscription_req_result_elem = $(
        ".user_group_subscription_request_result",
    ).expectOne();
    const html = render_user_group_membership_request_result({
        addition_success_messages,
        newly_added_member_count,
        already_added_member_count,
        newly_added_user_count,
        newly_added_subgroups_count,
        already_added_user_count,
        already_added_subgroups_count,
        total_member_count_exceeds_five,
        ignored_deactivated_groups_count,
        ignored_deactivated_users_count,
        ignored_deactivated_member_count,
    });
    scroll_util.get_content_element($user_group_subscription_req_result_elem).html(html);
}

export function edit_user_group_membership({
    group,
    added = [],
    removed = [],
    added_subgroups = [],
    removed_subgroups = [],
    success,
    error,
}: {
    group: UserGroup;
    added?: number[];
    removed?: number[];
    added_subgroups?: number[];
    removed_subgroups?: number[];
    success: () => void;
    error: (xhr?: JQuery.jqXHR) => void;
}): void {
    void channel.post({
        url: "/json/user_groups/" + group.id + "/members",
        data: {
            add: JSON.stringify(added),
            delete: JSON.stringify(removed),
            add_subgroups: JSON.stringify(added_subgroups),
            delete_subgroups: JSON.stringify(removed_subgroups),
        },
        success,
        error,
    });
}

function add_new_members({
    pill_user_ids,
    pill_group_ids,
}: {
    pill_user_ids: number[];
    pill_group_ids: number[];
}): void {
    const group = user_groups.get_user_group_from_id(current_group_id);
    if (!group) {
        return;
    }

    const deactivated_users = new Set<number>();
    const already_added_users = new Set<number>();

    const active_user_ids = pill_user_ids.filter((user_id) => {
        if (!people.is_person_active(user_id)) {
            deactivated_users.add(user_id);
            return false;
        }
        if (user_groups.is_user_in_group(group.id, user_id, true)) {
            // we filter out already added users before sending
            // add member request as the endpoint is not so robust and
            // fails complete request if any already added member
            // is present in the request.
            already_added_users.add(user_id);
            return false;
        }
        return true;
    });

    const user_id_set = new Set(active_user_ids);

    if (
        user_id_set.has(current_user.user_id) &&
        user_groups.is_user_in_group(group.id, current_user.user_id, true)
    ) {
        // We don't want to send a request to add ourselves if we
        // are already added to this group. This case occurs
        // when creating user pills from a stream or user group.
        user_id_set.delete(current_user.user_id);
    }

    let ignored_deactivated_users: User[] = [];
    let ignored_already_added_users: User[] = [];
    if (deactivated_users.size > 0) {
        const ignored_deactivated_users_ids = [...deactivated_users];
        ignored_deactivated_users = ignored_deactivated_users_ids.map((user_id) =>
            people.get_by_user_id(user_id),
        );
    }
    if (already_added_users.size > 0) {
        const ignored_already_added_users_ids = [...already_added_users];
        ignored_already_added_users = ignored_already_added_users_ids.map((user_id) =>
            people.get_by_user_id(user_id),
        );
    }

    const deactivated_groups = new Set<number>();
    const already_added_subgroups = new Set<number>();

    const existing_subgroup_ids = new Set(group.direct_subgroup_ids);
    const subgroup_ids_to_add = pill_group_ids.filter((group_id) => {
        const subgroup = user_groups.get_user_group_from_id(group_id);
        if (subgroup.deactivated) {
            deactivated_groups.add(group_id);
            return false;
        }

        if (existing_subgroup_ids.has(group_id)) {
            already_added_subgroups.add(group_id);
            return false;
        }

        return true;
    });

    let ignored_deactivated_groups: UserGroup[] = [];
    let ignored_already_added_subgroups: UserGroup[] = [];
    if (deactivated_groups.size > 0) {
        const ignored_deactivated_group_ids = [...deactivated_groups];
        ignored_deactivated_groups = ignored_deactivated_group_ids.map((group_id) =>
            user_groups.get_user_group_from_id(group_id),
        );
    }
    if (already_added_subgroups.size > 0) {
        const ignored_already_added_subgroup_ids = [...already_added_subgroups];
        ignored_already_added_subgroups = ignored_already_added_subgroup_ids.map((group_id) =>
            user_groups.get_user_group_from_id(group_id),
        );
    }

    const subgroup_id_set = new Set(subgroup_ids_to_add);

    const user_ids = [...user_id_set];
    const subgroup_ids = [...subgroup_id_set];
    const newly_added_users: User[] = user_ids.map((user_id) => people.get_by_user_id(user_id));
    const newly_added_subgroups: UserGroup[] = subgroup_ids.map((group_id) =>
        user_groups.get_user_group_from_id(group_id),
    );
    if (user_ids.length === 0 && subgroup_ids.length === 0) {
        // No need to make a network call and get the "Nothing to do..." response.
        // This will show a variation of "All users and groups were already members."
        // depending on whether the user attempted to added users or groups or a mix of both.
        pill_widget.clear();
        show_user_group_membership_request_success_result({
            newly_added_users,
            newly_added_subgroups,
            already_added_users: ignored_already_added_users,
            ignored_deactivated_users,
            already_added_subgroups: ignored_already_added_subgroups,
            ignored_deactivated_groups,
        });
        return;
    }

    const $pill_widget_button_wrapper = $(".add_member_button_wrapper");
    const $add_member_button = $pill_widget_button_wrapper.find(".add-member-button");
    $add_member_button.prop("disabled", true);
    $(".add_members_container").addClass("add_members_disabled");
    buttons.show_button_loading_indicator($add_member_button);
    function invite_success(): void {
        $(".add_members_container").removeClass("add_members_disabled");
        const $check_icon = $pill_widget_button_wrapper.find(".check");

        $check_icon.removeClass("hidden-below");
        $add_member_button.addClass("hidden-below");
        setTimeout(() => {
            $check_icon.addClass("hidden-below");
            $add_member_button.removeClass("hidden-below");
            buttons.hide_button_loading_indicator($add_member_button);
            // To undo the effect of hide_button_loading_indicator enabling the button.
            // This will keep the `Add` button disabled when input is empty.
            $add_member_button.prop("disabled", true);
        }, 1000);

        pill_widget.clear();
        show_user_group_membership_request_success_result({
            newly_added_users,
            newly_added_subgroups,
            already_added_users: ignored_already_added_users,
            ignored_deactivated_users,
            already_added_subgroups: ignored_already_added_subgroups,
            ignored_deactivated_groups,
        });
    }

    function invite_failure(xhr?: JQuery.jqXHR): void {
        $(".add_members_container").removeClass("add_members_disabled");
        buttons.hide_button_loading_indicator($add_member_button);

        let error_message = "Failed to add user!";

        const parsed = z
            .object({
                result: z.literal("error"),
                msg: z.string(),
            })
            .safeParse(xhr?.responseJSON);

        if (parsed.success) {
            error_message = parsed.data.msg;
        }
        show_user_group_membership_request_error_result(error_message);
    }

    edit_user_group_membership({
        group,
        added: user_ids,
        added_subgroups: subgroup_ids,
        success: invite_success,
        error: invite_failure,
    });
}

function remove_member({
    group_id,
    target_user_id,
    $list_entry,
    $remove_button,
}: {
    group_id: number;
    target_user_id: number;
    $list_entry: JQuery;
    $remove_button: JQuery;
}): void {
    const group = user_groups.get_user_group_from_id(current_group_id);
    if (!group) {
        return;
    }

    function removal_success(): void {
        if (group_id !== current_group_id) {
            blueslip.info("Response for subscription removal came too late.");
            return;
        }

        $list_entry.remove();
    }

    function removal_failure(): void {
        buttons.hide_button_loading_indicator($remove_button);
        const error_message = $t({defaultMessage: "Error removing user from this group."});
        show_user_group_membership_request_error_result(error_message);
    }

    function do_remove_user_from_group(): void {
        edit_user_group_membership({
            group,
            removed: [target_user_id],
            success: removal_success,
            error: removal_failure,
        });
    }

    if (people.is_my_user_id(target_user_id) && !settings_data.can_join_user_group(group_id)) {
        const html_body = render_leave_user_group_modal({
            message: $t({
                defaultMessage: "Once you leave this group, you will not be able to rejoin.",
            }),
        });

        confirm_dialog.launch({
            html_heading: $t_html(
                {defaultMessage: "Leave {group_name}"},
                {group_name: user_groups.get_display_group_name(group.name)},
            ),
            html_body,
            on_click: do_remove_user_from_group,
        });
        return;
    }

    do_remove_user_from_group();
}

function remove_subgroup({
    group_id,
    target_subgroup_id,
    $list_entry,
    $remove_button,
}: {
    group_id: number;
    target_subgroup_id: number;
    $list_entry: JQuery;
    $remove_button: JQuery;
}): void {
    const group = user_groups.get_user_group_from_id(current_group_id);

    function removal_success(): void {
        if (group_id !== current_group_id) {
            blueslip.info("Response for subgroup removal came too late.");
            return;
        }

        $list_entry.remove();
    }

    function removal_failure(): void {
        buttons.hide_button_loading_indicator($remove_button);
        const error_message = $t({defaultMessage: "Error removing subgroup from this group."});
        show_user_group_membership_request_error_result(error_message);
    }

    edit_user_group_membership({
        group,
        removed_subgroups: [target_subgroup_id],
        success: removal_success,
        error: removal_failure,
    });
}

export function initialize(): void {
    add_group_members_pill.set_up_handlers({
        get_pill_widget: () => pill_widget,
        $parent_container: $("#groups_overlay_container"),
        pill_selector: ".edit_members_for_user_group .pill-container",
        button_selector: ".edit_members_for_user_group .add-member-button",
        action: add_new_members,
    });

    $("#groups_overlay_container").on(
        "click",
        ".edit_members_for_user_group .remove-subscriber-button",
        function (this: HTMLElement, e): void {
            e.preventDefault();

            const $list_entry = $(this).closest("tr");
            const target_user_id = Number.parseInt($list_entry.attr("data-subscriber-id")!, 10);
            const group_id = current_group_id;
            const $remove_button = $(this).closest(".remove-subscriber-button");
            buttons.show_button_loading_indicator($remove_button);
            remove_member({group_id, target_user_id, $list_entry, $remove_button});
        },
    );

    $("#groups_overlay_container").on(
        "click",
        ".edit_members_for_user_group .remove-subgroup-button",
        function (this: HTMLElement, e): void {
            e.preventDefault();

            const $list_entry = $(this).closest("tr");
            const target_subgroup_id = Number.parseInt($list_entry.attr("data-subgroup-id")!, 10);
            const group_id = current_group_id;
            const $remove_button = $(this).closest(".remove-subgroup-button");
            buttons.show_button_loading_indicator($remove_button);
            remove_subgroup({group_id, target_subgroup_id, $list_entry, $remove_button});
        },
    );
}
