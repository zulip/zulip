import $ from "jquery";
import assert from "minimalistic-assert";
import {z} from "zod";

import render_leave_user_group_modal from "../templates/confirm_dialog/confirm_unsubscribe_private_stream.hbs";
import render_user_group_member_list_entry from "../templates/stream_settings/stream_member_list_entry.hbs";
import render_user_group_members_table from "../templates/user_group_settings/user_group_members_table.hbs";
import render_user_group_membership_request_result from "../templates/user_group_settings/user_group_membership_request_result.hbs";
import render_user_group_subgroup_entry from "../templates/user_group_settings/user_group_subgroup_entry.hbs";

import * as add_group_members_pill from "./add_group_members_pill.ts";
import * as blueslip from "./blueslip.ts";
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

function show_user_group_membership_request_result({
    message,
    add_class,
    remove_class,
    already_added_users,
    ignored_deactivated_users,
    already_added_subgroups,
    ignored_deactivated_groups,
}: {
    message: string;
    add_class: string;
    remove_class: string;
    already_added_users?: User[];
    ignored_deactivated_users?: User[];
    already_added_subgroups?: UserGroup[];
    ignored_deactivated_groups?: UserGroup[];
}): void {
    const $user_group_subscription_req_result_elem = $(
        ".user_group_subscription_request_result",
    ).expectOne();
    const html = render_user_group_membership_request_result({
        message,
        already_added_users,
        ignored_deactivated_users,
        already_added_subgroups,
        ignored_deactivated_groups,
    });
    scroll_util.get_content_element($user_group_subscription_req_result_elem).html(html);
    $user_group_subscription_req_result_elem.addClass(add_class);
    $user_group_subscription_req_result_elem.removeClass(remove_class);
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

    if (user_id_set.size === 0 && subgroup_id_set.size === 0) {
        show_user_group_membership_request_result({
            message: $t({defaultMessage: "No users or subgroups to add."}),
            add_class: "text-error",
            remove_class: "text-success",
            already_added_users: ignored_already_added_users,
            ignored_deactivated_users,
            already_added_subgroups: ignored_already_added_subgroups,
            ignored_deactivated_groups,
        });
        return;
    }
    const user_ids = [...user_id_set];
    const subgroup_ids = [...subgroup_id_set];

    function invite_success(): void {
        pill_widget.clear();
        show_user_group_membership_request_result({
            message: $t({defaultMessage: "Added successfully."}),
            add_class: "text-success",
            remove_class: "text-error",
            already_added_users: ignored_already_added_users,
            ignored_deactivated_users,
            already_added_subgroups: ignored_already_added_subgroups,
            ignored_deactivated_groups,
        });
    }

    function invite_failure(xhr?: JQuery.jqXHR): void {
        let message = "Failed to add user!";

        const parsed = z
            .object({
                result: z.literal("error"),
                msg: z.string(),
            })
            .safeParse(xhr?.responseJSON);

        if (parsed.success) {
            message = parsed.data.msg;
        }
        show_user_group_membership_request_result({
            message,
            add_class: "text-error",
            remove_class: "text-success",
        });
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
}: {
    group_id: number;
    target_user_id: number;
    $list_entry: JQuery;
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
        const message = $t({defaultMessage: "Removed successfully."});
        show_user_group_membership_request_result({
            message,
            add_class: "text-success",
            remove_class: "text-remove",
        });
    }

    function removal_failure(): void {
        show_user_group_membership_request_result({
            message: $t({defaultMessage: "Error removing user from this group."}),
            add_class: "text-error",
            remove_class: "text-success",
        });
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
}: {
    group_id: number;
    target_subgroup_id: number;
    $list_entry: JQuery;
}): void {
    const group = user_groups.get_user_group_from_id(current_group_id);

    function removal_success(): void {
        if (group_id !== current_group_id) {
            blueslip.info("Response for subgroup removal came too late.");
            return;
        }

        $list_entry.remove();
        const message = $t({defaultMessage: "Removed successfully."});
        show_user_group_membership_request_result({
            message,
            add_class: "text-success",
            remove_class: "text-remove",
        });
    }

    function removal_failure(): void {
        show_user_group_membership_request_result({
            message: $t({defaultMessage: "Error removing subgroup from this group."}),
            add_class: "text-error",
            remove_class: "text-success",
        });
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
        "submit",
        ".edit_members_for_user_group .subscriber_list_remove form",
        function (this: HTMLElement, e): void {
            e.preventDefault();

            const $list_entry = $(this).closest("tr");
            const target_user_id = Number.parseInt($list_entry.attr("data-subscriber-id")!, 10);
            const group_id = current_group_id;

            remove_member({group_id, target_user_id, $list_entry});
        },
    );

    $("#groups_overlay_container").on(
        "submit",
        ".edit_members_for_user_group .subgroup_list_remove form",
        function (this: HTMLElement, e): void {
            e.preventDefault();

            const $list_entry = $(this).closest("tr");
            const target_subgroup_id = Number.parseInt($list_entry.attr("data-subgroup-id")!, 10);
            const group_id = current_group_id;

            remove_subgroup({group_id, target_subgroup_id, $list_entry});
        },
    );
}
