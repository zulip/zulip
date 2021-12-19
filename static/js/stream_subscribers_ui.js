import $ from "jquery";

import render_unsubscribe_private_stream_modal from "../templates/confirm_dialog/confirm_unsubscribe_private_stream.hbs";
import render_stream_member_list_entry from "../templates/stream_settings/stream_member_list_entry.hbs";
import render_stream_subscription_request_result from "../templates/stream_settings/stream_subscription_request_result.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import {$t, $t_html} from "./i18n";
import * as input_pill from "./input_pill";
import * as ListWidget from "./list_widget";
import {page_params} from "./page_params";
import * as peer_data from "./peer_data";
import * as people from "./people";
import * as pill_typeahead from "./pill_typeahead";
import * as settings_data from "./settings_data";
import * as stream_pill from "./stream_pill";
import * as sub_store from "./sub_store";
import * as ui from "./ui";
import * as user_group_pill from "./user_group_pill";
import * as user_pill from "./user_pill";

export let pill_widget;

function create_item_from_text(text, current_items) {
    const funcs = [
        stream_pill.create_item_from_stream_name,
        user_group_pill.create_item_from_group_name,
        user_pill.create_item_from_email,
    ];
    for (const func of funcs) {
        const item = func(text, current_items);
        if (item) {
            return item;
        }
    }
    return undefined;
}

function get_text_from_item(item) {
    const funcs = [
        stream_pill.get_stream_name_from_item,
        user_group_pill.get_group_name_from_item,
        user_pill.get_email_from_item,
    ];
    for (const func of funcs) {
        const text = func(item);
        if (text) {
            return text;
        }
    }
    return undefined;
}

function format_member_list_elem(person) {
    return render_stream_member_list_entry({
        name: person.full_name,
        user_id: person.user_id,
        email: settings_data.email_for_user_settings(person),
        displaying_for_admin: page_params.is_admin,
        show_email: settings_data.show_email(),
    });
}

function get_stream_id(target) {
    // TODO: Use more precise selector.
    const row = $(target).closest(
        ".stream-row, .stream_settings_header, .subscription_settings, .save-button",
    );
    const stream_id = Number.parseInt(row.attr("data-stream-id"), 10);

    if (!stream_id) {
        blueslip.error("Cannot find stream id for target");
        return undefined;
    }

    return stream_id;
}

function get_sub(stream_id) {
    const sub = sub_store.get(stream_id);
    if (!sub) {
        blueslip.error("get_sub() failed id lookup: " + stream_id);
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
    const stream_subscription_req_result_elem = $(
        ".stream_subscription_request_result",
    ).expectOne();
    const html = render_stream_subscription_request_result({
        message,
        subscribed_users,
        already_subscribed_users,
        ignored_deactivated_users,
    });
    ui.get_content_element(stream_subscription_req_result_elem).html(html);
    if (add_class) {
        stream_subscription_req_result_elem.addClass(add_class);
    }
    if (remove_class) {
        stream_subscription_req_result_elem.removeClass(remove_class);
    }
}

export function enable_subscriber_management({sub, parent_container}) {
    const stream_id = sub.stream_id;

    const pill_container = parent_container.find(".pill-container");

    pill_widget = input_pill.create({
        container: pill_container,
        create_item_from_text,
        get_text_from_item,
    });

    const user_ids = peer_data.get_subscribers(stream_id);
    const users = people.get_users_from_ids(user_ids);
    people.sort_but_pin_current_user_on_top(users);

    function get_users_for_subscriber_typeahead() {
        const potential_subscribers = peer_data.potential_subscribers(stream_id);
        return user_pill.filter_taken_users(potential_subscribers, pill_widget);
    }

    const list_container = parent_container.find(".subscriber_table");
    list_container.empty();

    const simplebar_container = parent_container.find(".subscriber_list_container");

    ListWidget.create(list_container, users, {
        name: "stream_subscribers/" + stream_id,
        modifier(item) {
            return format_member_list_elem(item);
        },
        filter: {
            element: $(`[data-stream-id='${CSS.escape(stream_id)}'] .search`),
            predicate(person, value) {
                const matcher = people.build_person_matcher(value);
                const match = matcher(person);

                return match;
            },
        },
        simplebar_container,
    });

    const opts = {
        user_source: get_users_for_subscriber_typeahead,
        stream: true,
        user_group: true,
        user: true,
    };
    pill_typeahead.set_up(pill_container.find(".input"), pill_widget, opts);
}

export function invite_user_to_stream(user_ids, sub, success, failure) {
    // TODO: use stream_id when backend supports it
    const stream_name = sub.name;
    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {
            subscriptions: JSON.stringify([{name: stream_name}]),
            principals: JSON.stringify(user_ids),
        },
        success,
        error: failure,
    });
}

export function remove_user_from_stream(user_id, sub, success, failure) {
    // TODO: use stream_id when backend supports it
    const stream_name = sub.name;
    return channel.del({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([stream_name]), principals: JSON.stringify([user_id])},
        success,
        error: failure,
    });
}

function submit_add_subscriber_form(stream_id) {
    const sub = get_sub(stream_id);
    if (!sub) {
        return;
    }

    let user_ids = user_pill.get_user_ids(pill_widget);
    user_ids = user_ids.concat(stream_pill.get_user_ids(pill_widget));
    user_ids = user_ids.concat(user_group_pill.get_user_ids(pill_widget));
    const deactivated_users = new Set();
    user_ids = user_ids.filter((user_id) => {
        if (!people.is_person_active(user_id)) {
            deactivated_users.add(user_id);
            return false;
        }
        return true;
    });

    user_ids = new Set(user_ids);

    if (user_ids.has(page_params.user_id) && sub.subscribed) {
        // We don't want to send a request to subscribe ourselves
        // if we are already subscribed to this stream. This
        // case occurs when creating user pills from a stream.
        user_ids.delete(page_params.user_id);
    }
    let ignored_deactivated_users;
    if (deactivated_users.size > 0) {
        ignored_deactivated_users = Array.from(deactivated_users);
        ignored_deactivated_users = ignored_deactivated_users.map((user_id) =>
            people.get_by_user_id(user_id),
        );
    }
    if (user_ids.size === 0) {
        show_stream_subscription_request_result({
            message: $t({defaultMessage: "No user to subscribe."}),
            add_class: "text-error",
            remove_class: "text-success",
            ignored_deactivated_users,
        });
        return;
    }
    user_ids = Array.from(user_ids);

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
        const error = JSON.parse(xhr.responseText);
        show_stream_subscription_request_result({
            message: error.msg,
            add_class: "text-error",
            remove_class: "text-success",
        });
    }

    invite_user_to_stream(user_ids, sub, invite_success, invite_failure);
}

function remove_subscriber({stream_id, target_user_id, list_entry}) {
    const sub = get_sub(stream_id);
    if (!sub) {
        return;
    }
    let message;

    function removal_success(data) {
        if (data.removed.length > 0) {
            // Remove the user from the subscriber list.
            list_entry.remove();
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
            message: $t({defaultMessage: "Error removing user from this stream."}),
            add_class: "text-error",
            remove_class: "text-success",
        });
    }

    function remove_user_from_private_stream() {
        remove_user_from_stream(target_user_id, sub, removal_success, removal_failure);
    }

    if (sub.invite_only && people.is_my_user_id(target_user_id)) {
        const html_body = render_unsubscribe_private_stream_modal();

        confirm_dialog.launch({
            html_heading: $t_html(
                {defaultMessage: "Unsubscribe from {stream_name}"},
                {stream_name: sub.name},
            ),
            html_body,
            on_click: remove_user_from_private_stream,
        });
        return;
    }

    remove_user_from_stream(target_user_id, sub, removal_success, removal_failure);
}

export function initialize() {
    $("#subscriptions_table").on("keyup", ".subscriber_list_add form", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            const stream_id = get_stream_id(e.target);
            submit_add_subscriber_form(stream_id);
        }
    });

    $("#subscriptions_table").on("submit", ".subscriber_list_add form", (e) => {
        e.preventDefault();
        const stream_id = get_stream_id(e.target);
        submit_add_subscriber_form(stream_id);
    });

    $("#subscriptions_table").on("submit", ".subscriber_list_remove form", (e) => {
        e.preventDefault();

        const list_entry = $(e.target).closest("tr");
        const target_user_id = Number.parseInt(list_entry.attr("data-subscriber-id"), 10);
        const stream_id = get_stream_id(e.target);

        remove_subscriber({stream_id, target_user_id, list_entry});
    });
}
