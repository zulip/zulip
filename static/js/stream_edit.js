import $ from "jquery";

import render_settings_deactivation_stream_modal from "../templates/confirm_dialog/confirm_deactivate_stream.hbs";
import render_unsubscribe_private_stream_modal from "../templates/confirm_dialog/confirm_unsubscribe_private_stream.hbs";
import render_change_stream_info_modal from "../templates/stream_settings/change_stream_info_modal.hbs";
import render_stream_description from "../templates/stream_settings/stream_description.hbs";
import render_stream_member_list_entry from "../templates/stream_settings/stream_member_list_entry.hbs";
import render_stream_privacy_setting_modal from "../templates/stream_settings/stream_privacy_setting_modal.hbs";
import render_stream_settings from "../templates/stream_settings/stream_settings.hbs";
import render_stream_subscription_request_result from "../templates/stream_settings/stream_subscription_request_result.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as channel from "./channel";
import * as components from "./components";
import * as confirm_dialog from "./confirm_dialog";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as input_pill from "./input_pill";
import * as ListWidget from "./list_widget";
import * as narrow_state from "./narrow_state";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as peer_data from "./peer_data";
import * as people from "./people";
import * as pill_typeahead from "./pill_typeahead";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as settings_ui from "./settings_ui";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import * as stream_pill from "./stream_pill";
import * as stream_settings_data from "./stream_settings_data";
import * as stream_settings_ui from "./stream_settings_ui";
import * as stream_ui_updates from "./stream_ui_updates";
import * as sub_store from "./sub_store";
import * as ui from "./ui";
import * as ui_report from "./ui_report";
import * as user_group_pill from "./user_group_pill";
import * as user_pill from "./user_pill";
import {user_settings} from "./user_settings";
import * as util from "./util";

export let pill_widget;
export let toggler;
export let select_tab = "personal_settings";

function setup_subscriptions_stream_hash(sub) {
    const hash = hash_util.stream_edit_uri(sub);
    browser_history.update(hash);
}

function compare_by_email(a, b) {
    if (a.delivery_email && b.delivery_email) {
        return util.strcmp(a.delivery_email, b.delivery_email);
    }
    return util.strcmp(a.email, b.email);
}

function compare_by_name(a, b) {
    return util.strcmp(a.full_name, b.full_name);
}

export function setup_subscriptions_tab_hash(tab_key_value) {
    if (tab_key_value === "all-streams") {
        browser_history.update("#streams/all");
    } else if (tab_key_value === "subscribed") {
        browser_history.update("#streams/subscribed");
    } else {
        blueslip.debug("Unknown tab_key_value: " + tab_key_value);
    }
}

export function settings_for_sub(sub) {
    return $(
        `#subscription_overlay .subscription_settings[data-stream-id='${CSS.escape(
            sub.stream_id,
        )}']`,
    );
}

export function is_sub_settings_active(sub) {
    // This function return whether the provided given sub object is
    // currently being viewed/edited in the stream edit UI.  This is
    // used to determine whether we need to rerender the stream edit
    // UI when a sub object is modified by an event.
    const active_stream = hash_util.active_stream();
    if (active_stream !== undefined && active_stream.id === sub.stream_id) {
        return true;
    }
    return false;
}

export function get_users_from_subscribers(subscribers) {
    return subscribers.map((user_id) => people.get_by_user_id(user_id));
}

export function get_retention_policy_text_for_subscription_type(sub) {
    let message_retention_days = sub.message_retention_days;
    // If both this stream and the organization-level policy are to retain forever,
    // there's no need to comment on retention policies when describing the stream.
    if (
        page_params.realm_message_retention_days === settings_config.retain_message_forever &&
        (sub.message_retention_days === null ||
            sub.message_retention_days === settings_config.retain_message_forever)
    ) {
        return undefined;
    }

    // Forever for this stream, overriding the organization default
    if (sub.message_retention_days === settings_config.retain_message_forever) {
        return $t({defaultMessage: "Messages in this stream will be retained forever."});
    }

    // If we are deleting messages, even if it's the organization
    // default, it's worth commenting on the policy.
    if (message_retention_days === null) {
        message_retention_days = page_params.realm_message_retention_days;
    }

    return $t(
        {
            defaultMessage:
                "Messages in this stream will be automatically deleted after {retention_days} days.",
        },
        {retention_days: message_retention_days},
    );
}

export function get_display_text_for_realm_message_retention_setting() {
    const realm_message_retention_days = page_params.realm_message_retention_days;
    if (realm_message_retention_days === settings_config.retain_message_forever) {
        return $t({defaultMessage: "(forever)"});
    }
    return $t(
        {defaultMessage: "({message_retention_days} days)"},
        {message_retention_days: realm_message_retention_days},
    );
}

function change_stream_message_retention_days_block_display_property(value) {
    if (value === "retain_for_period") {
        $(".stream-message-retention-days-input").show();
    } else {
        $(".stream-message-retention-days-input").hide();
    }
}

function set_stream_message_retention_setting_dropdown(stream) {
    let value = "retain_for_period";
    if (stream.message_retention_days === null) {
        value = "realm_default";
    } else if (stream.message_retention_days === settings_config.retain_message_forever) {
        value = "unlimited";
    }

    $(".stream_message_retention_setting").val(value);
    change_stream_message_retention_days_block_display_property(value);
}

function get_stream_id(target) {
    const row = $(target).closest(
        ".stream-row, .stream_settings_header, .subscription_settings, .save-button",
    );
    return Number.parseInt(row.attr("data-stream-id"), 10);
}

function get_sub_for_target(target) {
    const stream_id = get_stream_id(target);
    if (!stream_id) {
        blueslip.error("Cannot find stream id for target");
        return undefined;
    }

    const sub = sub_store.get(stream_id);
    if (!sub) {
        blueslip.error("get_sub_for_target() failed id lookup: " + stream_id);
        return undefined;
    }
    return sub;
}

export function open_edit_panel_for_row(stream_row) {
    const sub = get_sub_for_target(stream_row);

    $(".stream-row.active").removeClass("active");
    stream_settings_ui.show_subs_pane.settings(sub.name);
    $(stream_row).addClass("active");
    setup_subscriptions_stream_hash(sub);
    setup_stream_settings(stream_row);
}

export function open_edit_panel_empty() {
    const tab_key = $(stream_settings_ui.get_active_data().tabs[0]).attr("data-tab-key");
    $(".stream-row.active").removeClass("active");
    stream_settings_ui.show_subs_pane.nothing_selected();
    setup_subscriptions_tab_hash(tab_key);
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

function get_subscriber_list(sub_row) {
    const stream_id_str = sub_row.data("stream-id");
    return $(
        `.subscription_settings[data-stream-id="${CSS.escape(stream_id_str)}"] .subscriber-list`,
    );
}

export function update_stream_name(sub, new_name) {
    const sub_settings = settings_for_sub(sub);
    sub_settings.find(".email-address").text(sub.email_address);
    sub_settings.find(".sub-stream-name").text(new_name);
}

export function update_stream_description(sub) {
    const stream_settings = settings_for_sub(sub);
    stream_settings.find("input.description").val(sub.description);
    const html = render_stream_description({
        rendered_description: util.clean_user_content_links(sub.rendered_description),
    });
    stream_settings.find(".stream-description").html(html);
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

function submit_add_subscriber_form(e) {
    const sub = get_sub_for_target(e.target);
    if (!sub) {
        blueslip.error(".subscriber_list_add form submit fails");
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

export function sort_but_pin_current_user_on_top(users) {
    if (users === undefined) {
        blueslip.error("Undefined users are passed to function sort_but_pin_current_user_on_top");
        return;
    }

    const my_user = people.get_by_email(people.my_current_email());
    let compare_function;
    if (settings_data.show_email()) {
        compare_function = compare_by_email;
    } else {
        compare_function = compare_by_name;
    }
    if (users.includes(my_user)) {
        users.splice(users.indexOf(my_user), 1);
        users.sort(compare_function);
        users.unshift(my_user);
    } else {
        users.sort(compare_function);
    }
}

export function create_item_from_text(text, current_items) {
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

export function get_text_from_item(item) {
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

function show_subscription_settings(sub) {
    const stream_id = sub.stream_id;
    const sub_settings = settings_for_sub(sub);

    const colorpicker = sub_settings.find(".colorpicker");
    const color = stream_data.get_color(sub.name);
    stream_color.set_colorpicker_color(colorpicker, color);
    stream_ui_updates.update_add_subscriptions_elements(sub);

    if (!sub.render_subscribers) {
        return;
    }

    const container = $(
        `#subscription_overlay .subscription_settings[data-stream-id='${CSS.escape(
            stream_id,
        )}'] .pill-container`,
    );

    pill_widget = input_pill.create({
        container,
        create_item_from_text,
        get_text_from_item,
    });

    if (!stream_data.can_toggle_subscription(sub)) {
        stream_ui_updates.initialize_cant_subscribe_popover(sub);
    }
    // fetch subscriber list from memory.
    const list = get_subscriber_list(sub_settings);
    list.empty();

    const user_ids = peer_data.get_subscribers(sub.stream_id);
    const users = get_users_from_subscribers(user_ids);
    sort_but_pin_current_user_on_top(users);

    function get_users_for_subscriber_typeahead() {
        const potential_subscribers = peer_data.potential_subscribers(stream_id);
        return user_pill.filter_taken_users(potential_subscribers, pill_widget);
    }

    ListWidget.create(list, users, {
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
        simplebar_container: $(".subscriber_list_container"),
    });

    const opts = {
        user_source: get_users_for_subscriber_typeahead,
        stream: true,
        user_group: true,
        user: true,
    };
    pill_typeahead.set_up(sub_settings.find(".input"), pill_widget, opts);
}

export function is_notification_setting(setting_label) {
    if (setting_label.includes("_notifications")) {
        return true;
    } else if (setting_label.includes("_notify")) {
        return true;
    }
    return false;
}

export function stream_settings(sub) {
    const settings_labels = settings_config.general_notifications_table_labels.stream;
    const check_realm_setting =
        settings_config.all_notifications(user_settings).show_push_notifications_tooltip;

    const settings = Object.keys(settings_labels).map((setting) => {
        const ret = {
            name: setting,
            label: settings_labels[setting],
            disabled_realm_setting: check_realm_setting[setting],
            is_disabled: check_realm_setting[setting],
            is_notification_setting: is_notification_setting(setting),
        };
        if (is_notification_setting(setting)) {
            // This block ensures we correctly display to users the
            // current state of stream-level notification settings
            // with a value of `null`, which inherit the user's global
            // notification settings for streams.
            ret.is_checked =
                stream_data.receives_notifications(sub.stream_id, setting) &&
                !check_realm_setting[setting];
            ret.is_disabled = ret.is_disabled || sub.is_muted;
            return ret;
        }
        ret.is_checked = sub[setting] && !check_realm_setting[setting];
        return ret;
    });
    return settings;
}

export function show_settings_for(node) {
    const stream_id = get_stream_id(node);
    const slim_sub = sub_store.get(stream_id);
    stream_data.clean_up_description(slim_sub);
    const sub = stream_settings_data.get_sub_for_settings(slim_sub);
    const all_settings = stream_settings(sub);

    const other_settings = [];
    const notification_settings = all_settings.filter((setting) => {
        if (setting.is_notification_setting) {
            return true;
        }
        other_settings.push(setting);
        return false;
    });

    const html = render_stream_settings({
        sub,
        notification_settings,
        other_settings,
        stream_post_policy_values: stream_data.stream_post_policy_values,
        message_retention_text: get_retention_policy_text_for_subscription_type(sub),
    });
    ui.get_content_element($("#stream_settings")).html(html);

    $("#stream_settings .tab-container").prepend(toggler.get());
    stream_ui_updates.update_toggler_for_sub(sub);

    const sub_settings = settings_for_sub(sub);

    $(".nothing-selected").hide();
    $("#subscription_overlay .stream_change_property_info").hide();

    sub_settings.addClass("show");

    show_subscription_settings(sub);
}

export function setup_stream_settings(node) {
    toggler = components.toggle({
        child_wants_focus: true,
        values: [
            {label: $t({defaultMessage: "General"}), key: "general_settings"},
            {label: $t({defaultMessage: "Personal"}), key: "personal_settings"},
            {label: $t({defaultMessage: "Subscribers"}), key: "subscriber_settings"},
        ],
        callback(name, key) {
            $(".stream_section").hide();
            $("." + key).show();
            select_tab = key;
        },
    });

    show_settings_for(node);
}

function stream_is_muted_changed(e) {
    const sub = get_sub_for_target(e.target);
    if (!sub) {
        blueslip.error("stream_is_muted_changed() fails");
        return;
    }

    const sub_settings = settings_for_sub(sub);
    const notification_checkboxes = sub_settings.find(".sub_notification_setting");

    stream_settings_ui.set_muted(
        sub,
        e.target.checked,
        `#stream_change_property_status${CSS.escape(sub.stream_id)}`,
    );
    sub_settings.find(".mute-note").toggleClass("hide-mute-note", !sub.is_muted);
    notification_checkboxes.toggleClass("muted-sub", sub.is_muted);
    notification_checkboxes.find("input[type='checkbox']").prop("disabled", sub.is_muted);
}

export function stream_setting_changed(e, from_notification_settings) {
    if (e.target.name === "is_muted") {
        return;
    }

    const sub = get_sub_for_target(e.target);
    const status_element = from_notification_settings
        ? $(e.target).closest(".subsection-parent").find(".alert-notification")
        : $(`#stream_change_property_status${CSS.escape(sub.stream_id)}`);
    const setting = e.target.name;
    if (!sub) {
        blueslip.error("undefined sub in stream_setting_changed()");
        return;
    }
    if (is_notification_setting(setting) && sub[setting] === null) {
        if (setting === "wildcard_mentions_notify") {
            sub[setting] = user_settings[setting];
        } else {
            sub[setting] = user_settings["enable_stream_" + setting];
        }
    }
    set_stream_property(sub, setting, e.target.checked, status_element);
}

export function bulk_set_stream_property(sub_data, status_element) {
    const url = "/json/users/me/subscriptions/properties";
    const data = {subscription_data: JSON.stringify(sub_data)};
    if (!status_element) {
        return channel.post({
            url,
            data,
            timeout: 10 * 1000,
        });
    }

    settings_ui.do_settings_change(channel.post, url, data, status_element);
    return undefined;
}

export function set_stream_property(sub, property, value, status_element) {
    const sub_data = {stream_id: sub.stream_id, property, value};
    bulk_set_stream_property([sub_data], status_element);
}

function get_message_retention_days_from_sub(sub) {
    if (sub.message_retention_days === null) {
        return "realm_default";
    }
    if (sub.message_retention_days === -1) {
        return "unlimited";
    }
    return sub.message_retention_days;
}

function change_stream_privacy(e) {
    e.stopPropagation();

    const data = {};
    const stream_id = $(e.target).data("stream-id");
    const url = "/json/streams/" + stream_id;
    const status_element = $(".stream_permission_change_info");
    const sub = sub_store.get(stream_id);

    const privacy_setting = $("#stream_privacy_modal input[name=privacy]:checked").val();
    const stream_post_policy = Number.parseInt(
        $("#stream_privacy_modal input[name=stream-post-policy]:checked").val(),
        10,
    );

    if (sub.stream_post_policy !== stream_post_policy) {
        data.stream_post_policy = JSON.stringify(stream_post_policy);
    }

    let invite_only;
    let history_public_to_subscribers;
    let is_web_public;

    switch (privacy_setting) {
        case stream_data.stream_privacy_policy_values.public.code: {
            invite_only = false;
            history_public_to_subscribers = true;
            is_web_public = false;

            break;
        }
        case stream_data.stream_privacy_policy_values.private.code: {
            invite_only = true;
            history_public_to_subscribers = false;
            is_web_public = false;

            break;
        }
        case stream_data.stream_privacy_policy_values.web_public.code: {
            invite_only = false;
            history_public_to_subscribers = true;
            is_web_public = true;

            break;
        }
        default: {
            invite_only = true;
            history_public_to_subscribers = true;
            is_web_public = false;
        }
    }

    if (
        sub.invite_only !== invite_only ||
        sub.history_public_to_subscribers !== history_public_to_subscribers ||
        sub.is_web_public !== is_web_public
    ) {
        data.is_private = JSON.stringify(invite_only);
        data.history_public_to_subscribers = JSON.stringify(history_public_to_subscribers);
        data.is_web_public = JSON.stringify(is_web_public);
    }

    let message_retention_days = $(
        "#stream_privacy_modal select[name=stream_message_retention_setting]",
    ).val();
    if (message_retention_days === "retain_for_period") {
        message_retention_days = Number.parseInt(
            $("#stream_privacy_modal input[name=stream-message-retention-days]").val(),
            10,
        );
    }

    const message_retention_days_from_sub = get_message_retention_days_from_sub(sub);

    if (message_retention_days_from_sub !== message_retention_days) {
        data.message_retention_days = JSON.stringify(message_retention_days);
    }

    overlays.close_modal("#stream_privacy_modal");

    if (Object.keys(data).length === 0) {
        return;
    }

    settings_ui.do_settings_change(channel.patch, url, data, status_element);
}

export function archive_stream(stream_id, alert_element, stream_row) {
    channel.del({
        url: "/json/streams/" + stream_id,
        error(xhr) {
            ui_report.error($t_html({defaultMessage: "Failed"}), xhr, alert_element);
        },
        success() {
            stream_row.remove();
        },
    });
}

export function initialize() {
    $("#main_div").on("click", ".stream_sub_unsub_button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const sub = narrow_state.stream_sub();
        if (sub === undefined) {
            return;
        }

        stream_settings_ui.sub_or_unsub(sub);
    });

    $("#subscriptions_table").on("click", ".change-stream-privacy", (e) => {
        const stream_id = get_stream_id(e.target);
        const stream = sub_store.get(stream_id);

        const template_data = {
            stream_id,
            stream_name: stream.name,
            stream_privacy_policy_values: stream_data.stream_privacy_policy_values,
            stream_privacy_policy: stream_data.get_stream_privacy_policy(stream_id),
            stream_post_policy_values: stream_data.stream_post_policy_values,
            stream_post_policy: stream.stream_post_policy,
            is_owner: page_params.is_owner,
            zulip_plan_is_not_limited: page_params.zulip_plan_is_not_limited,
            disable_message_retention_setting:
                !page_params.zulip_plan_is_not_limited || !page_params.is_owner,
            stream_message_retention_days: stream.message_retention_days,
            org_level_message_retention_setting:
                get_display_text_for_realm_message_retention_setting(),
            upgrade_text_for_wide_organization_logo:
                page_params.upgrade_text_for_wide_organization_logo,
            is_stream_edit: true,
        };
        const change_privacy_modal = render_stream_privacy_setting_modal(template_data);
        $("#stream_privacy_modal").remove();
        $("#subscriptions_table").append(change_privacy_modal);
        set_stream_message_retention_setting_dropdown(stream);
        overlays.open_modal("#stream_privacy_modal");
        e.preventDefault();
        e.stopPropagation();
    });

    $("#subscriptions_table").on("click", "#change-stream-privacy-button", change_stream_privacy);

    $("#subscriptions_table").on("click", "#open_stream_info_modal", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const stream_id = get_stream_id(e.target);
        const stream = sub_store.get(stream_id);
        const template_data = {
            stream_id,
            stream_name: stream.name,
            stream_description: stream.description,
        };
        const change_stream_info_modal = render_change_stream_info_modal(template_data);
        $("#change_stream_info_modal").remove();
        $("#subscriptions_table").append(change_stream_info_modal);
        overlays.open_modal("#change_stream_info_modal");
    });

    $("#subscriptions_table").on("keypress", "#change_stream_description", (e) => {
        // Stream descriptions can not be multiline, so disable enter key
        // to prevent new line
        if (e.key === "Enter") {
            return false;
        }
        return true;
    });

    $("#subscriptions_table").on("click", "#save_stream_info", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const sub = get_sub_for_target(e.currentTarget);

        const url = `/json/streams/${sub.stream_id}`;
        const data = {};
        const new_name = $("#change_stream_name").val().trim();
        const new_description = $("#change_stream_description").val().trim();

        if (new_name === sub.name && new_description === sub.description) {
            return;
        }
        if (new_name !== sub.name) {
            data.new_name = new_name;
        }
        if (new_description !== sub.description) {
            data.description = new_description;
        }

        const status_element = $(".stream_change_property_info");
        overlays.close_modal("#change_stream_info_modal");
        settings_ui.do_settings_change(channel.patch, url, data, status_element);
    });

    $("#subscriptions_table").on(
        "click",
        ".close-modal-btn, .close-change-stream-info-modal",
        (e) => {
            // This fixes a weird bug in which, subscription_settings hides
            // unexpectedly by clicking the cancel button in a modal on top of it.
            e.stopPropagation();
        },
    );

    $("#subscriptions_table").on(
        "change",
        "#sub_is_muted_setting .sub_setting_control",
        stream_is_muted_changed,
    );

    $("#subscriptions_table").on(
        "change",
        ".sub_setting_checkbox .sub_setting_control",
        stream_setting_changed,
    );

    $("#subscriptions_table").on("keyup", ".subscriber_list_add form", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            submit_add_subscriber_form(e);
        }
    });

    $("#subscriptions_table").on("submit", ".subscriber_list_add form", (e) => {
        e.preventDefault();
        submit_add_subscriber_form(e);
    });

    $("#subscriptions_table").on("submit", ".subscriber_list_remove form", (e) => {
        e.preventDefault();

        const list_entry = $(e.target).closest("tr");
        const target_user_id = Number.parseInt(list_entry.attr("data-subscriber-id"), 10);

        const sub = get_sub_for_target(e.target);
        if (!sub) {
            blueslip.error(".subscriber_list_remove form submit fails");
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
    });

    // This handler isn't part of the normal edit interface; it's the convenient
    // checkmark in the subscriber list.
    $("#subscriptions_table").on("click", ".sub_unsub_button", (e) => {
        const sub = get_sub_for_target(e.target);
        // Makes sure we take the correct stream_row.
        const stream_row = $(
            `#subscriptions_table div.stream-row[data-stream-id='${CSS.escape(sub.stream_id)}']`,
        );
        stream_settings_ui.sub_or_unsub(sub, stream_row);

        if (!sub.subscribed) {
            open_edit_panel_for_row(stream_row);
        }
        stream_ui_updates.update_regular_sub_settings(sub);

        e.preventDefault();
        e.stopPropagation();
    });

    $("#subscriptions_table").on("click", ".deactivate", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const stream_id = get_stream_id(e.target);
        if (!stream_id) {
            ui_report.client_error(
                $t_html({defaultMessage: "Invalid stream id"}),
                $(".stream_change_property_info"),
            );
            return;
        }

        function do_archive_stream() {
            const stream_id = $(".dialog_submit_button").data("stream-id");
            if (!stream_id) {
                ui_report.client_error(
                    $t_html({defaultMessage: "Invalid stream id"}),
                    $(".stream_change_property_info"),
                );
                return;
            }
            const row = $(".stream-row.active");
            archive_stream(stream_id, $(".stream_change_property_info"), row);
        }

        const stream_name = stream_data.maybe_get_stream_name(stream_id);
        const html_body = render_settings_deactivation_stream_modal({
            stream_name,
        });

        confirm_dialog.launch({
            html_heading: $t_html(
                {defaultMessage: "Archive stream {stream}"},
                {stream: stream_name},
            ),
            help_link: "/help/archive-a-stream",
            html_body,
            on_click: do_archive_stream,
        });

        $(".dialog_submit_button").attr("data-stream-id", stream_id);
    });

    $("#subscriptions_table").on("click", ".stream-row", function (e) {
        if ($(e.target).closest(".check, .subscription_settings").length === 0) {
            open_edit_panel_for_row(this);
        }
    });

    $("#subscriptions_table").on("change", ".stream_message_retention_setting", (e) => {
        const dropdown_value = e.target.value;
        change_stream_message_retention_days_block_display_property(dropdown_value);
    });
}
