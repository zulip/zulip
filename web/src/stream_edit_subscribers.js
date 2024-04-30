import $ from "jquery";

import render_unsubscribe_private_stream_modal from "../templates/confirm_dialog/confirm_unsubscribe_private_stream.hbs";
import render_inline_decorated_stream_name from "../templates/inline_decorated_stream_name.hbs";
import render_stream_member_list_entry from "../templates/stream_settings/stream_member_list_entry.hbs";
import render_stream_members from "../templates/stream_settings/stream_members.hbs";
import render_stream_subscription_request_result from "../templates/stream_settings/stream_subscription_request_result.hbs";

import * as add_subscribers_pill from "./add_subscribers_pill";
import * as blueslip from "./blueslip";
import * as confirm_dialog from "./confirm_dialog";
import * as hash_parser from "./hash_parser";
import {$t, $t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as peer_data from "./peer_data";
import * as people from "./people";
import * as scroll_util from "./scroll_util";
import {current_user} from "./state_data";
import * as stream_data from "./stream_data";
import * as stream_settings_containers from "./stream_settings_containers";
import * as sub_store from "./sub_store";
import * as subscriber_api from "./subscriber_api";
import * as user_sort from "./user_sort";

export let pill_widget;
let current_stream_id;
let subscribers_list_widget;

function format_member_list_elem(person, user_can_remove_subscribers) {
    return render_stream_member_list_entry({
        name: person.full_name,
        user_id: person.user_id,
        is_current_user: person.user_id === current_user.user_id,
        email: person.delivery_email,
        can_remove_subscribers: user_can_remove_subscribers,
        for_user_group_members: false,
        img_src: people.small_avatar_url_for_person(person),
    });
}

function get_sub(stream_id) {
    const sub = sub_store.get(stream_id);
    if (!sub) {
        blueslip.error("get_sub() failed id lookup", {stream_id});
        return undefined;
    }
    return sub;
}

function show_stream_subscription_request_result({
    message,
    add_class,
    remove_class,
    subscribed_users,
    already_subscribed_users,
    ignored_deactivated_users,
}) {
    const $stream_subscription_req_result_elem = $(
        ".stream_subscription_request_result",
    ).expectOne();
    const html = render_stream_subscription_request_result({
        message,
        subscribed_users,
        already_subscribed_users,
        ignored_deactivated_users,
    });
    scroll_util.get_content_element($stream_subscription_req_result_elem).html(html);
    if (add_class) {
        $stream_subscription_req_result_elem.addClass(add_class);
    }
    if (remove_class) {
        $stream_subscription_req_result_elem.removeClass(remove_class);
    }
}

export function enable_subscriber_management({sub, $parent_container}) {
    const stream_id = sub.stream_id;

    const $pill_container = $parent_container.find(".pill-container");

    // current_stream_id and pill_widget are module-level variables
    current_stream_id = stream_id;

    function get_potential_subscribers() {
        return peer_data.potential_subscribers(stream_id);
    }

    pill_widget = add_subscribers_pill.create({
        $pill_container,
        get_potential_subscribers,
    });

    $pill_container.find(".input").on("input", () => {
        $parent_container.find(".stream_subscription_request_result").empty();
    });

    const user_ids = peer_data.get_subscribers(stream_id);
    const user_can_remove_subscribers = stream_data.can_unsubscribe_others(sub);

    // We track a single subscribers_list_widget for this module, since we
    // only ever have one list of subscribers visible at a time.
    subscribers_list_widget = make_list_widget({
        $parent_container,
        name: "stream_subscribers",
        user_ids,
        user_can_remove_subscribers,
    });
}

function make_list_widget({$parent_container, name, user_ids, user_can_remove_subscribers}) {
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
            $element: $parent_container.find(".search"),
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

function subscribe_new_users({pill_user_ids}) {
    const sub = get_sub(current_stream_id);
    if (!sub) {
        return;
    }

    const deactivated_users = new Set();
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
    let ignored_deactivated_users;
    if (deactivated_users.size > 0) {
        ignored_deactivated_users = [...deactivated_users];
        ignored_deactivated_users = ignored_deactivated_users.map((user_id) =>
            people.get_by_user_id(user_id),
        );
    }
    if (user_id_set.size === 0) {
        show_stream_subscription_request_result({
            message: $t({defaultMessage: "No user to subscribe."}),
            add_class: "text-error",
            remove_class: "text-success",
            ignored_deactivated_users,
        });
        return;
    }

    const user_ids = [...user_id_set];

    function invite_success(data) {
        pill_widget.clear();
        const subscribed_users = Object.keys(data.subscribed).map((email) =>
            people.get_by_email(email),
        );
        const already_subscribed_users = Object.keys(data.already_subscribed).map((email) =>
            people.get_by_email(email),
        );

        show_stream_subscription_request_result({
            add_class: "text-success",
            remove_class: "text-error",
            subscribed_users,
            already_subscribed_users,
            ignored_deactivated_users,
        });
    }

    function invite_failure(xhr) {
        let message = "Failed to subscribe user!";
        if (xhr.responseJSON?.msg) {
            message = xhr.responseJSON.msg;
        }
        show_stream_subscription_request_result({
            message,
            add_class: "text-error",
            remove_class: "text-success",
        });
    }

    subscriber_api.add_user_ids_to_stream(user_ids, sub, invite_success, invite_failure);
}

function remove_subscriber({stream_id, target_user_id, $list_entry}) {
    const sub = get_sub(stream_id);
    if (!sub) {
        return;
    }

    function removal_success(data) {
        let message;

        if (stream_id !== current_stream_id) {
            blueslip.info("Response for subscription removal came too late.");
            return;
        }

        if (data.removed.length > 0) {
            // Remove the user from the subscriber list.
            $list_entry.remove();
            message = $t({defaultMessage: "Unsubscribed successfully!"});
            // The rest of the work is done via the subscription -> remove event we will get
        } else {
            message = $t({defaultMessage: "User is already not subscribed."});
        }
        show_stream_subscription_request_result({
            message,
            add_class: "text-success",
            remove_class: "text-remove",
        });
    }

    function removal_failure() {
        show_stream_subscription_request_result({
            message: $t({defaultMessage: "Error removing user from this channel."}),
            add_class: "text-error",
            remove_class: "text-success",
        });
    }

    function remove_user_from_private_stream() {
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

        const stream_name_with_privacy_symbol_html = render_inline_decorated_stream_name({
            stream: sub,
        });

        const html_body = render_unsubscribe_private_stream_modal({
            unsubscribing_other_user,
            display_stream_archive_warning: sub_count === 1,
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

export function update_subscribers_list(sub) {
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
        $(".subscriber_list_settings_container").show();
    }
}

function update_subscribers_list_widget(subscriber_ids) {
    // This re-renders the subscribers_list_widget with a new
    // list of subscriber_ids.
    const users = people.get_users_from_ids(subscriber_ids);
    people.sort_but_pin_current_user_on_top(users);
    subscribers_list_widget.replace_list_data(users);
}

export function rerender_subscribers_list(sub) {
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

    const user_ids = peer_data.get_subscribers(sub.stream_id);
    const user_can_remove_subscribers = stream_data.can_unsubscribe_others(sub);
    const $parent_container = stream_settings_containers
        .get_edit_container(sub)
        .find(".edit_subscribers_for_stream");

    $parent_container.html(
        render_stream_members({
            can_access_subscribers: true,
            can_remove_subscribers: user_can_remove_subscribers,
            render_subscribers: sub.render_subscribers,
        }),
    );
    subscribers_list_widget = make_list_widget({
        $parent_container,
        name: "stream_subscribers",
        user_ids,
        user_can_remove_subscribers,
    });
}

export function initialize() {
    add_subscribers_pill.set_up_handlers({
        get_pill_widget: () => pill_widget,
        $parent_container: $("#channels_overlay_container"),
        pill_selector: ".edit_subscribers_for_stream .pill-container",
        button_selector: ".edit_subscribers_for_stream .add-subscriber-button",
        action: subscribe_new_users,
    });

    $("#channels_overlay_container").on(
        "submit",
        ".edit_subscribers_for_stream .subscriber_list_remove form",
        (e) => {
            e.preventDefault();

            const $list_entry = $(e.target).closest("tr");
            const target_user_id = Number.parseInt($list_entry.attr("data-subscriber-id"), 10);
            const stream_id = current_stream_id;

            remove_subscriber({stream_id, target_user_id, $list_entry});
        },
    );
}
