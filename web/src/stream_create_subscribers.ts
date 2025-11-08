import $ from "jquery";

import render_new_stream_user from "../templates/stream_settings/new_stream_user.hbs";
import render_new_stream_users from "../templates/stream_settings/new_stream_users.hbs";

import * as add_subscribers_pill from "./add_subscribers_pill.ts";
import * as ListWidget from "./list_widget.ts";
import type {ListWidget as ListWidgetType} from "./list_widget.ts";
import * as people from "./people.ts";
import {current_user} from "./state_data.ts";
import * as stream_create_subscribers_data from "./stream_create_subscribers_data.ts";
import type {CombinedPillContainer} from "./typeahead_helper.ts";
import * as user_groups from "./user_groups.ts";
import * as user_pill from "./user_pill.ts";
import * as user_sort from "./user_sort.ts";

export let pill_widget: CombinedPillContainer;
let all_users_list_widget: ListWidgetType<number, people.User>;

export function get_principals(): number[] {
    return stream_create_subscribers_data.get_principals();
}

function redraw_subscriber_list(): void {
    all_users_list_widget.replace_list_data(stream_create_subscribers_data.sorted_user_ids());
}

function add_user_ids(user_ids: number[]): void {
    stream_create_subscribers_data.add_user_ids(user_ids);
    redraw_subscriber_list();
}

function soft_remove_user_id(user_id: number): void {
    stream_create_subscribers_data.soft_remove_user_id(user_id);
    redraw_subscriber_list();
}

function undo_soft_remove_user_id(user_id: number): void {
    stream_create_subscribers_data.undo_soft_remove_user_id(user_id);
    redraw_subscriber_list();
}

function sync_user_ids(user_ids: number[]): void {
    stream_create_subscribers_data.sync_user_ids(user_ids);
    redraw_subscriber_list();
}

function build_pill_widget({
    $parent_container,
}: {
    $parent_container: JQuery;
}): CombinedPillContainer {
    const $pill_container = $parent_container.find(".pill-container");
    const get_potential_subscribers = stream_create_subscribers_data.get_potential_subscribers;
    const get_user_groups = user_groups.get_all_realm_user_groups;
    return add_subscribers_pill.create({
        $pill_container,
        get_potential_subscribers,
        get_user_groups,
        with_add_button: false,
        onPillCreateAction: add_user_ids,
        // It is better to sync the current set of user ids in the input
        // instead of removing user_ids from the user_ids_set, otherwise
        // we'll have to have more complex logic of when to remove
        // a user and when not to depending upon their group, channel
        // and individual pills.
        onPillRemoveAction: sync_user_ids,
    });
}

export function create_handlers($container: JQuery): void {
    $container.on("click", ".remove_potential_subscriber", function (this: HTMLElement, e) {
        e.preventDefault();
        const $subscriber_row = $(this).closest(".settings-subscriber-row");
        const user_id = Number.parseInt($subscriber_row.attr("data-user-id")!, 10);
        soft_remove_user_id(user_id);
    });

    $container.on(
        "click",
        ".undo_soft_removed_potential_subscriber",
        function (this: HTMLElement, e) {
            e.preventDefault();
            const $subscriber_row = $(this).closest(".settings-subscriber-row");
            const user_id = Number.parseInt($subscriber_row.attr("data-user-id")!, 10);
            undo_soft_remove_user_id(user_id);
        },
    );
}

export function build_widgets(): void {
    const $add_people_container = $("#people_to_add");
    $add_people_container.html(render_new_stream_users({}));

    const $simplebar_container = $add_people_container.find(".subscriber_list_container");

    pill_widget = build_pill_widget({$parent_container: $add_people_container});

    stream_create_subscribers_data.initialize_with_current_user();
    const current_user_id = current_user.user_id;

    all_users_list_widget = ListWidget.create($("#create_stream_subscribers"), [current_user_id], {
        name: "new_stream_add_users",
        get_item: people.get_by_user_id,
        $parent_container: $add_people_container,
        modifier_html(user) {
            const item = {
                email: user.delivery_email,
                user_id: user.user_id,
                full_name: user.full_name,
                is_current_user: user.user_id === current_user_id,
                img_src: people.small_avatar_url_for_person(user),
                soft_removed: stream_create_subscribers_data.user_id_in_soft_remove_list(
                    user.user_id,
                ),
            };
            return render_new_stream_user(item);
        },
        sort_fields: {
            email: user_sort.sort_email,
            id: user_sort.sort_user_id,
            ...ListWidget.generic_sort_functions("alphabetic", ["full_name"]),
        },
        filter: {
            $element: $("#people_to_add .add-user-list-filter"),
            predicate(user, search_term) {
                return people.build_person_matcher(search_term)(user);
            },
        },
        $simplebar_container,
        html_selector(user) {
            return $(`#${CSS.escape("user_checkbox_" + user.user_id)}`);
        },
    });
    const current_person = people.get_by_user_id(current_user.user_id);
    user_pill.append_user(current_person, pill_widget);
}

export function add_user_id_to_new_stream(user_id: number): void {
    // This is only used by puppeteer tests.
    add_user_ids([user_id]);
}
