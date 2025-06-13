import Handlebars from "handlebars/runtime.js";
import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_unsubscribe_private_stream_modal from "../templates/confirm_dialog/confirm_unsubscribe_private_stream.hbs";
import render_inline_decorated_channel_name from "../templates/inline_decorated_channel_name.hbs";
import render_stream_member_list_entry from "../templates/stream_settings/stream_member_list_entry.hbs";
import render_stream_members_table from "../templates/stream_settings/stream_members_table.hbs";
import render_stream_subscription_request_result from "../templates/stream_settings/stream_subscription_request_result.hbs";

import * as add_subscribers_pill from "./add_subscribers_pill.ts";
import * as blueslip from "./blueslip.ts";
import * as buttons from "./buttons.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as hash_parser from "./hash_parser.ts";
import {$t, $t_html} from "./i18n.ts";
import * as ListWidget from "./list_widget.ts";
import type {ListWidget as ListWidgetType} from "./list_widget.ts";
import * as loading from "./loading.ts";
import * as peer_data from "./peer_data.ts";
import * as people from "./people.ts";
import type {User} from "./people.ts";
import * as scroll_util from "./scroll_util.ts";
import {current_user, realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_settings_containers from "./stream_settings_containers.ts";
import type {SettingsSubscription} from "./stream_settings_data.ts";
import * as sub_store from "./sub_store.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as subscriber_api from "./subscriber_api.ts";
import type {CombinedPillContainer} from "./typeahead_helper.ts";
import * as user_groups from "./user_groups.ts";
import * as user_sort from "./user_sort.ts";
import * as util from "./util.ts";

const remove_user_id_api_response_schema = z.object({
    removed: z.array(z.string()),
    not_removed: z.array(z.string()),
});

const add_user_ids_api_response_schema = z.object({
    subscribed: z.record(z.string(), z.array(z.string())),
    already_subscribed: z.record(z.string(), z.array(z.string())),
});

export let pill_widget: CombinedPillContainer;
let current_stream_id: number;
let subscribers_list_widget: ListWidgetType<User, User>;

function format_member_list_elem(person: User, user_can_remove_subscribers: boolean): string {
    return render_stream_member_list_entry({
        name: person.full_name,
        user_id: person.user_id,
        is_current_user: person.user_id === current_user.user_id,
        email: person.delivery_email,
        can_remove_subscribers: user_can_remove_subscribers,
        for_user_group_members: false,
        img_src: people.small_avatar_url_for_person(person),
        is_bot: person.is_bot,
    });
}

function get_sub(stream_id: number): StreamSubscription | undefined {
    const sub = sub_store.get(stream_id);
    if (!sub) {
        blueslip.error("get_sub() failed id lookup", {stream_id});
        return undefined;
    }
    return sub;
}

function generate_subscribe_success_messages(
    subscribed_users: User[],
    already_subscribed_users: User[],
    ignored_deactivated_users: User[],
): {
    subscribed_users_message_html: string;
    already_subscribed_users_message_html: string;
    ignored_deactivated_users_message_html: string;
} {
    const subscribed_user_links = subscribed_users.map(
        (user) =>
            `<a data-user-id="${user.user_id}" class="view_user_profile">${Handlebars.Utils.escapeExpression(user.full_name)}</a>`,
    );
    const already_subscribed_user_links = already_subscribed_users.map(
        (user) =>
            `<a data-user-id="${user.user_id}" class="view_user_profile">${Handlebars.Utils.escapeExpression(user.full_name)}</a>`,
    );
    const ignored_deactivated_user_links = ignored_deactivated_users.map(
        (user) =>
            `<a data-user-id="${user.user_id}" class="view_user_profile">${Handlebars.Utils.escapeExpression(user.full_name)}</a>`,
    );

    const subscribed_users_message_html = util.format_array_as_list_with_conjunction(
        subscribed_user_links,
        "long",
    );
    const already_subscribed_users_message_html = util.format_array_as_list_with_conjunction(
        already_subscribed_user_links,
        "long",
    );
    const ignored_deactivated_users_message_html = util.format_array_as_list_with_conjunction(
        ignored_deactivated_user_links,
        "long",
    );
    return {
        subscribed_users_message_html,
        already_subscribed_users_message_html,
        ignored_deactivated_users_message_html,
    };
}

function show_stream_subscription_request_error_result(error_message: string): void {
    const $stream_subscription_req_result_elem = $(
        ".stream_subscription_request_result",
    ).expectOne();
    const html = render_stream_subscription_request_result({
        error_message,
    });
    scroll_util.get_content_element($stream_subscription_req_result_elem).html(html);
}

function show_stream_subscription_request_success_result({
    subscribed_users,
    already_subscribed_users,
    ignored_deactivated_users,
}: {
    subscribed_users: User[];
    already_subscribed_users: User[];
    ignored_deactivated_users: User[];
}): void {
    const subscribed_users_count = subscribed_users.length;
    const already_subscribed_users_count = already_subscribed_users.length;
    const ignored_deactivated_users_count = ignored_deactivated_users.length;
    const is_total_subscriber_more_than_five =
        subscribed_users_count + already_subscribed_users_count + ignored_deactivated_users_count >
        5;

    const $stream_subscription_req_result_elem = $(
        ".stream_subscription_request_result",
    ).expectOne();

    let subscribe_success_messages;
    if (!is_total_subscriber_more_than_five) {
        subscribe_success_messages = generate_subscribe_success_messages(
            subscribed_users,
            already_subscribed_users,
            ignored_deactivated_users,
        );
    }
    const html = render_stream_subscription_request_result({
        subscribe_success_messages,
        subscribed_users,
        already_subscribed_users,
        subscribed_users_count,
        already_subscribed_users_count,
        is_total_subscriber_more_than_five,
        ignored_deactivated_users,
        ignored_deactivated_users_count,
    });
    scroll_util.get_content_element($stream_subscription_req_result_elem).html(html);
}

function update_notification_choice_checkbox(added_user_count: number): void {
    const $send_notification_checkbox = $(".send_notification_to_new_subscribers");
    const $send_notification_container = $(".send_notification_to_new_subscribers_container");
    if (added_user_count > realm.max_bulk_new_subscription_messages) {
        $send_notification_checkbox.prop("checked", false);
        $send_notification_checkbox.prop("disabled", true);
        $send_notification_container.addClass("control-label-disabled");
    } else {
        $send_notification_checkbox.prop("disabled", false);
        $send_notification_container.removeClass("control-label-disabled");
    }
}

async function stream_edit_update_notification_choice(): Promise<void> {
    const pill_count = (await add_subscribers_pill.get_pill_user_ids(pill_widget)).length;
    update_notification_choice_checkbox(pill_count);
}

export function enable_subscriber_management({
    sub,
    $parent_container,
}: {
    sub: SettingsSubscription;
    $parent_container: JQuery;
}): void {
    const stream_id = sub.stream_id;

    const $pill_container = $parent_container.find(".pill-container");

    // current_stream_id and pill_widget are module-level variables
    current_stream_id = stream_id;

    function get_potential_subscribers(): User[] {
        return peer_data.potential_subscribers(stream_id);
    }

    const update_notification_choice = function (): void {
        void stream_edit_update_notification_choice();
    };
    pill_widget = add_subscribers_pill.create({
        $pill_container,
        get_potential_subscribers,
        onPillCreateAction: update_notification_choice,
        onPillRemoveAction: update_notification_choice,
        add_button_pill_update_callback: update_notification_choice,
        get_user_groups: user_groups.get_all_realm_user_groups,
        with_add_button: true,
    });

    $pill_container.find(".input").on("input", () => {
        $parent_container.find(".stream_subscription_request_result").empty();
    });

    const user_can_remove_subscribers = stream_data.can_unsubscribe_others(sub);
    void render_subscriber_list_widget(sub, user_can_remove_subscribers, $parent_container);
}

async function render_subscriber_list_widget(
    sub: StreamSubscription,
    user_can_remove_subscribers: boolean,
    $parent_container: JQuery,
): Promise<void> {
    $(".subscriber_list_settings_container").toggleClass("no-display", true);
    loading.make_indicator($(".subscriber-list-settings-loading"), {
        text: $t({defaultMessage: "Loading…"}),
    });

    // Because we're using `retry_on_failure=true`, this will only return once it
    // succeeds, so we can't get `null`.
    const user_ids = await peer_data.get_all_subscribers(sub.stream_id, true);
    assert(user_ids !== null);

    // Make sure we're still editing this stream after waiting for subscriber data.
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        blueslip.info("ignoring subscriber data for stream that is no longer being edited");
        return;
    }

    // We track a single subscribers_list_widget for this module, since we
    // only ever have one list of subscribers visible at a time.
    subscribers_list_widget = make_list_widget({
        $parent_container,
        name: "stream_subscribers",
        user_ids,
        user_can_remove_subscribers,
    });
    loading.destroy_indicator($(".subscriber-list-settings-loading"));
    $(".subscriber_list_settings_container").toggleClass("no-display", false);
}

function make_list_widget({
    $parent_container,
    name,
    user_ids,
    user_can_remove_subscribers,
}: {
    $parent_container: JQuery;
    name: string;
    user_ids: number[];
    user_can_remove_subscribers: boolean;
}): ListWidgetType<User, User> {
    const users = people.get_users_from_ids(user_ids);
    people.sort_but_pin_current_user_on_top(users);

    const $list_container = $parent_container.find(".subscriber_table");
    $list_container.empty();

    const $simplebar_container = $parent_container.find(".subscriber_list_container");

    return ListWidget.create($list_container, users, {
        name,
        get_item: ListWidget.default_get_item,
        modifier_html(item) {
            return format_member_list_elem(item, user_can_remove_subscribers);
        },
        filter: {
            $element: $parent_container.find<HTMLInputElement>("input.search"),
            predicate(person, value) {
                const matcher = people.build_person_matcher(value);
                const match = matcher(person);

                return match;
            },
        },
        $parent_container: $("#stream_members_list").expectOne(),
        sort_fields: {
            email: user_sort.sort_email,
            id: user_sort.sort_user_id,
            ...ListWidget.generic_sort_functions("alphabetic", ["full_name"]),
        },
        $simplebar_container,
    });
}

function subscribe_new_users({pill_user_ids}: {pill_user_ids: number[]}): void {
    const sub = get_sub(current_stream_id);
    if (!sub) {
        return;
    }

    const deactivated_users = new Set<number>();
    const active_user_ids = pill_user_ids.filter((user_id) => {
        if (!people.is_person_active(user_id)) {
            deactivated_users.add(user_id);
            return false;
        }
        return true;
    });

    const user_id_set = new Set(active_user_ids);

    if (user_id_set.has(current_user.user_id) && sub.subscribed) {
        // We don't want to send a request to subscribe ourselves
        // if we are already subscribed to this stream. This
        // case occurs when creating user pills from a stream.
        user_id_set.delete(current_user.user_id);
    }
    let ignored_deactivated_users: User[] = [];
    if (deactivated_users.size > 0) {
        const ignored_deactivated_user_ids = [...deactivated_users];
        ignored_deactivated_users = ignored_deactivated_user_ids.map((user_id) =>
            people.get_by_user_id(user_id),
        );
    }

    const user_ids = [...user_id_set];
    if (user_ids.length === 0) {
        // No need to make a network call in this case.
        // This will show "All users were already subscribed."
        pill_widget.clear();
        show_stream_subscription_request_success_result({
            subscribed_users: [],
            already_subscribed_users: [],
            ignored_deactivated_users,
        });
        return;
    }

    const $pill_widget_button_wrapper = $(".add_subscriber_button_wrapper");
    const $add_subscriber_button = $pill_widget_button_wrapper.find(".add-subscriber-button");
    $add_subscriber_button.prop("disabled", true);
    $(".add_subscribers_container").addClass("add_subscribers_disabled");
    buttons.show_button_loading_indicator($add_subscriber_button);

    function invite_success(raw_data: unknown): void {
        $(".add_subscribers_container").removeClass("add_subscribers_disabled");
        const data = add_user_ids_api_response_schema.parse(raw_data);
        pill_widget.clear();
        const subscribed_users = Object.keys(data.subscribed).map((user_id) =>
            people.get_by_user_id(Number(user_id)),
        );
        const already_subscribed_users = Object.keys(data.already_subscribed).map((user_id) =>
            people.get_by_user_id(Number(user_id)),
        );

        const $check_icon = $pill_widget_button_wrapper.find(".check");

        $check_icon.removeClass("hidden-below");
        $add_subscriber_button.addClass("hidden-below");
        setTimeout(() => {
            $check_icon.addClass("hidden-below");
            $add_subscriber_button.removeClass("hidden-below");
            buttons.hide_button_loading_indicator($add_subscriber_button);
            // To undo the effect of hide_button_loading_indicator enabling the button.
            // This will keep the `Add` button disabled when input is empty.
            $add_subscriber_button.prop("disabled", true);
        }, 1000);

        show_stream_subscription_request_success_result({
            subscribed_users,
            already_subscribed_users,
            ignored_deactivated_users,
        });
    }

    function invite_failure(xhr: JQuery.jqXHR): void {
        buttons.hide_button_loading_indicator($add_subscriber_button);
        $(".add_subscribers_container").removeClass("add_subscribers_disabled");

        let error_message = "Failed to subscribe user!";
        const parsed = z
            .object({
                result: z.literal("error"),
                msg: z.string(),
                code: z.string(),
            })
            .safeParse(xhr.responseJSON);

        if (parsed.success) {
            error_message = parsed.data.msg;
        }
        show_stream_subscription_request_error_result(error_message);
    }

    subscriber_api.add_user_ids_to_stream(
        user_ids,
        sub,
        $("#send_notification_to_new_subscribers").is(":checked"),
        invite_success,
        invite_failure,
    );
}

function remove_subscriber({
    stream_id,
    target_user_id,
    $list_entry,
    $remove_button,
}: {
    stream_id: number;
    target_user_id: number;
    $list_entry: JQuery;
    $remove_button: JQuery;
}): void {
    const sub = get_sub(stream_id);
    if (!sub) {
        return;
    }

    function removal_success(raw_data: unknown): void {
        const data = remove_user_id_api_response_schema.parse(raw_data);

        if (stream_id !== current_stream_id) {
            blueslip.info("Response for subscription removal came too late.");
            return;
        }

        if (data.removed.length > 0) {
            // Remove the user from the subscriber list.
            $list_entry.remove();
            // The rest of the work is done via the subscription -> remove event we will get
        }
    }

    function removal_failure(): void {
        buttons.hide_button_loading_indicator($remove_button);
        const error_message = $t({defaultMessage: "Error removing user from this channel."});
        show_stream_subscription_request_error_result(error_message);
    }

    function remove_user_from_private_stream(): void {
        assert(sub !== undefined);
        subscriber_api.remove_user_id_from_stream(
            target_user_id,
            sub,
            removal_success,
            removal_failure,
        );
    }

    if (sub.invite_only) {
        const sub_count = peer_data.get_subscriber_count(stream_id);
        const unsubscribing_other_user = !people.is_my_user_id(target_user_id);

        if (!people.is_my_user_id(target_user_id) && sub_count !== 1) {
            // We do not show any confirmation modal if any other user is
            // being unsubscribed and that user is not the last subscriber
            // of that stream.
            remove_user_from_private_stream();
            return;
        }

        if (
            people.is_my_user_id(target_user_id) &&
            stream_data.has_content_access_via_group_permissions(sub)
        ) {
            // We do not show any confirmation modal if user is unsubscribing
            // themseleves and also has the permission to subscribe to the
            // stream again.
            remove_user_from_private_stream();
            return;
        }

        const stream_name_with_privacy_symbol_html = render_inline_decorated_channel_name({
            stream: sub,
        });

        const html_body = render_unsubscribe_private_stream_modal({
            unsubscribing_other_user,
            organization_will_lose_content_access:
                sub_count === 1 &&
                user_groups.is_setting_group_set_to_nobody_group(sub.can_subscribe_group) &&
                user_groups.is_setting_group_set_to_nobody_group(sub.can_add_subscribers_group),
        });

        let html_heading;
        if (unsubscribing_other_user) {
            html_heading = $t_html(
                {defaultMessage: "Unsubscribe {full_name} from <z-link></z-link>?"},
                {
                    full_name: people.get_full_name(target_user_id),
                    "z-link": () => stream_name_with_privacy_symbol_html,
                },
            );
        } else {
            html_heading = $t_html(
                {defaultMessage: "Unsubscribe from <z-link></z-link>?"},
                {"z-link": () => stream_name_with_privacy_symbol_html},
            );
        }

        confirm_dialog.launch({
            html_heading,
            html_body,
            on_click: remove_user_from_private_stream,
        });
        return;
    }

    subscriber_api.remove_user_id_from_stream(
        target_user_id,
        sub,
        removal_success,
        removal_failure,
    );
}

export function update_subscribers_list(sub: StreamSubscription): void {
    // This is for the "Subscribers" tab of the right panel.
    // Render subscriptions only if stream settings is open
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        return;
    }

    if (sub.stream_id !== current_stream_id) {
        // This should never happen if the prior check works correctly.
        blueslip.error("current_stream_id does not match sub.stream_id for some reason");
        return;
    }

    if (!stream_data.can_view_subscribers(sub)) {
        $(".subscriber_list_settings_container").hide();
    } else {
        // Re-render the whole list when we add new users.  This is
        // inefficient for the single-user case, but using the big-hammer
        // approach is superior when you do things like add subscribers
        // from an existing stream or a user group.
        const subscriber_ids = peer_data.get_subscribers(sub.stream_id);
        update_subscribers_list_widget(subscriber_ids);
    }
}

function update_subscribers_list_widget(subscriber_ids: number[]): void {
    // This can happen if we're still fetching user ids in
    // `render_subscriber_list_widget`, but we'll render the widget with
    // fetched ids after the fetch is complete, so we don't need to do
    // anything here.
    if (subscribers_list_widget === undefined) {
        return;
    }
    // This re-renders the subscribers_list_widget with a new
    // list of subscriber_ids.
    const users = people.get_users_from_ids(subscriber_ids);
    people.sort_but_pin_current_user_on_top(users);
    subscribers_list_widget.replace_list_data(users);
    $(".subscriber_list_settings_container").show();
}

export function rerender_subscribers_list(sub: sub_store.StreamSubscription): void {
    if (!hash_parser.is_editing_stream(sub.stream_id)) {
        blueslip.info("ignoring subscription for stream that is no longer being edited");
        return;
    }

    if (sub.stream_id !== current_stream_id) {
        // This should never happen if the prior check works correctly.
        blueslip.error("current_stream_id does not match sub.stream_id for some reason");
        return;
    }

    if (!stream_data.can_view_subscribers(sub)) {
        return;
    }

    const user_can_remove_subscribers = stream_data.can_unsubscribe_others(sub);
    const $parent_container = stream_settings_containers
        .get_edit_container(sub)
        .find(".edit_subscribers_for_stream");

    $parent_container.find(".subscriber-list-box").html(
        render_stream_members_table({
            can_remove_subscribers: user_can_remove_subscribers,
        }),
    );
    void render_subscriber_list_widget(sub, user_can_remove_subscribers, $parent_container);
}

export function initialize(): void {
    add_subscribers_pill.set_up_handlers({
        get_pill_widget: () => pill_widget,
        $parent_container: $("#channels_overlay_container"),
        pill_selector: ".edit_subscribers_for_stream .pill-container",
        button_selector: ".edit_subscribers_for_stream .add-subscriber-button",
        action: subscribe_new_users,
    });

    $("#channels_overlay_container").on(
        "click",
        ".edit_subscribers_for_stream .remove-subscriber-button",
        function (this: HTMLElement, e): void {
            e.preventDefault();

            const $list_entry = $(this).closest("tr");
            const target_user_id = Number.parseInt($list_entry.attr("data-subscriber-id")!, 10);
            const stream_id = current_stream_id;
            const $remove_button = $(this).closest(".remove-subscriber-button");
            buttons.show_button_loading_indicator($remove_button);
            remove_subscriber({stream_id, target_user_id, $list_entry, $remove_button});
        },
    );
}
