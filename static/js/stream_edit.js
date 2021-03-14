import $ from "jquery";

import render_settings_deactivation_stream_modal from "../templates/settings/deactivation_stream_modal.hbs";
import render_stream_member_list_entry from "../templates/stream_member_list_entry.hbs";
import render_stream_subscription_info from "../templates/stream_subscription_info.hbs";
import render_subscription_settings from "../templates/subscription_settings.hbs";
import render_subscription_stream_privacy_modal from "../templates/subscription_stream_privacy_modal.hbs";

import * as channel from "./channel";
import * as hash_util from "./hash_util";
import * as hashchange from "./hashchange";
import * as input_pill from "./input_pill";
import * as ListWidget from "./list_widget";
import * as narrow_state from "./narrow_state";
import * as overlays from "./overlays";
import * as peer_data from "./peer_data";
import * as people from "./people";
import * as pill_typeahead from "./pill_typeahead";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as settings_ui from "./settings_ui";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import * as stream_pill from "./stream_pill";
import * as stream_ui_updates from "./stream_ui_updates";
import * as subs from "./subs";
import * as ui from "./ui";
import * as ui_report from "./ui_report";
import * as user_pill from "./user_pill";
import * as util from "./util";

export let pill_widget;

function setup_subscriptions_stream_hash(sub) {
    const hash = hash_util.stream_edit_uri(sub);
    hashchange.update_browser_history(hash);
}

function compare_by_email(a, b) {
    if (a.delivery_email && b.delivery_email) {
        return a.delivery_email.localeCompare(b.delivery_email);
    }
    return a.email.localeCompare(b.email);
}

function compare_by_name(a, b) {
    return a.full_name.localeCompare(b.full_name);
}

export function setup_subscriptions_tab_hash(tab_key_value) {
    if (tab_key_value === "all-streams") {
        hashchange.update_browser_history("#streams/all");
    } else if (tab_key_value === "subscribed") {
        hashchange.update_browser_history("#streams/subscribed");
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
    const active_stream = subs.active_stream();
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
        return i18n.t("Messages in this stream will be retained forever.");
    }

    // If we are deleting messages, even if it's the organization
    // default, it's worth commenting on the policy.
    if (message_retention_days === null) {
        message_retention_days = page_params.realm_message_retention_days;
    }

    return i18n.t(
        "Messages in this stream will be automatically deleted after __retention_days__ days.",
        {retention_days: message_retention_days},
    );
}

export function get_display_text_for_realm_message_retention_setting() {
    const realm_message_retention_days = page_params.realm_message_retention_days;
    if (realm_message_retention_days === settings_config.retain_message_forever) {
        return i18n.t("(forever)");
    }
    return i18n.t("(__message_retention_days__ days)", {
        message_retention_days: realm_message_retention_days,
    });
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
        value = "forever";
    }

    $(".stream_message_retention_setting").val(value);
    change_stream_message_retention_days_block_display_property(value);
}

function get_stream_id(target) {
    const row = $(target).closest(".stream-row, .subscription_settings");
    return Number.parseInt(row.attr("data-stream-id"), 10);
}

function get_sub_for_target(target) {
    const stream_id = get_stream_id(target);
    if (!stream_id) {
        blueslip.error("Cannot find stream id for target");
        return undefined;
    }

    const sub = stream_data.get_sub_by_id(stream_id);
    if (!sub) {
        blueslip.error("get_sub_for_target() failed id lookup: " + stream_id);
        return undefined;
    }
    return sub;
}

export function open_edit_panel_for_row(stream_row) {
    const sub = get_sub_for_target(stream_row);

    $(".stream-row.active").removeClass("active");
    subs.show_subs_pane.settings();
    $(stream_row).addClass("active");
    setup_subscriptions_stream_hash(sub);
    show_settings_for(stream_row);
}

export function open_edit_panel_empty() {
    const tab_key = $(subs.get_active_data().tabs[0]).attr("data-tab-key");
    $(".stream-row.active").removeClass("active");
    subs.show_subs_pane.nothing_selected();
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
    sub_settings.find(".stream-name-editable").text(new_name);
}

export function update_stream_description(sub) {
    const stream_settings = settings_for_sub(sub);
    stream_settings.find("input.description").val(sub.description);
    stream_settings
        .find(".stream-description-editable")
        .html(util.clean_user_content_links(sub.rendered_description));
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

function submit_add_subscriber_form(e) {
    const sub = get_sub_for_target(e.target);
    if (!sub) {
        blueslip.error(".subscriber_list_add form submit fails");
        return;
    }

    const stream_subscription_info_elem = $(".stream_subscription_info").expectOne();
    let user_ids = user_pill.get_user_ids(pill_widget);
    user_ids = user_ids.concat(stream_pill.get_user_ids(pill_widget));
    user_ids = new Set(user_ids);

    if (user_ids.has(page_params.user_id) && sub.subscribed) {
        // We don't want to send a request to subscribe ourselves
        // if we are already subscribed to this stream. This
        // case occurs when creating user pills from a stream.
        user_ids.delete(page_params.user_id);
    }
    if (user_ids.size === 0) {
        stream_subscription_info_elem
            .text(i18n.t("No user to subscribe."))
            .addClass("text-error")
            .removeClass("text-success");
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

        const html = render_stream_subscription_info({subscribed_users, already_subscribed_users});
        ui.get_content_element(stream_subscription_info_elem).html(html);
        stream_subscription_info_elem.addClass("text-success").removeClass("text-error");
    }

    function invite_failure(xhr) {
        const error = JSON.parse(xhr.responseText);
        stream_subscription_info_elem
            .text(error.msg)
            .addClass("text-error")
            .removeClass("text-success");
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
    const item = stream_pill.create_item_from_stream_name(text, current_items);
    if (item) {
        return item;
    }
    return user_pill.create_item_from_email(text, current_items);
}

export function get_text_from_item(item) {
    const text = stream_pill.get_stream_name_from_item(item);
    if (text) {
        return text;
    }
    return user_pill.get_email_from_item(item);
}

function show_subscription_settings(sub) {
    const stream_id = sub.stream_id;
    const sub_settings = settings_for_sub(sub);

    const colorpicker = sub_settings.find(".colorpicker");
    const color = stream_data.get_color(sub.name);
    stream_color.set_colorpicker_color(colorpicker, color);
    stream_ui_updates.update_add_subscriptions_elements(sub);

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

    if (!sub.render_subscribers) {
        return;
    }
    if (!sub.should_display_subscription_button) {
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
            predicate(item, value) {
                const person = item;

                if (person) {
                    if (
                        person.email.toLocaleLowerCase().includes(value) &&
                        settings_data.show_email()
                    ) {
                        return true;
                    }
                    return person.full_name.toLowerCase().includes(value);
                }

                return false;
            },
        },
        simplebar_container: $(".subscriber_list_container"),
    });

    const opts = {source: get_users_for_subscriber_typeahead, stream: true};
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
    const check_realm_setting = settings_config.all_notifications().show_push_notifications_tooltip;

    const settings = Object.keys(settings_labels).map((setting) => {
        const ret = {
            name: setting,
            label: settings_labels[setting],
            disabled_realm_setting: check_realm_setting[setting],
            is_disabled: check_realm_setting[setting],
            is_notification_setting: is_notification_setting(setting),
        };
        if (is_notification_setting(setting)) {
            ret.is_checked = sub[setting + "_display"] && !check_realm_setting[setting];
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
    const sub = stream_data.get_sub_by_id(stream_id);

    stream_data.update_calculated_fields(sub);
    const html = render_subscription_settings({
        sub,
        settings: stream_settings(sub),
        stream_post_policy_values: stream_data.stream_post_policy_values,
        message_retention_text: get_retention_policy_text_for_subscription_type(sub),
    });
    ui.get_content_element($(".subscriptions .right .settings")).html(html);

    const sub_settings = settings_for_sub(sub);

    $(".nothing-selected").hide();

    sub_settings.addClass("show");

    show_subscription_settings(sub);
}

function stream_is_muted_changed(e) {
    const sub = get_sub_for_target(e.target);
    if (!sub) {
        blueslip.error("stream_is_muted_changed() fails");
        return;
    }

    const sub_settings = settings_for_sub(sub);
    const notification_checkboxes = sub_settings.find(".sub_notification_setting");

    subs.set_muted(
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
            sub[setting] = page_params[setting];
        } else {
            sub[setting] = page_params["enable_stream_" + setting];
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
        return "forever";
    }
    return sub.message_retention_days;
}

function change_stream_privacy(e) {
    e.stopPropagation();

    const stream_id = $(e.target).data("stream-id");
    const sub = stream_data.get_sub_by_id(stream_id);
    const data = {};
    const stream_privacy_status = $(".stream-privacy-status");
    stream_privacy_status.hide();

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

    if (privacy_setting === stream_data.stream_privacy_policy_values.public.code) {
        invite_only = false;
        history_public_to_subscribers = true;
    } else if (privacy_setting === stream_data.stream_privacy_policy_values.private.code) {
        invite_only = true;
        history_public_to_subscribers = false;
    } else {
        invite_only = true;
        history_public_to_subscribers = true;
    }

    if (
        sub.invite_only !== invite_only ||
        sub.history_public_to_subscribers !== history_public_to_subscribers
    ) {
        data.is_private = JSON.stringify(invite_only);
        data.history_public_to_subscribers = JSON.stringify(history_public_to_subscribers);
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

    $(".stream_change_property_info").hide();

    if (Object.keys(data).length === 0) {
        overlays.close_modal("#stream_privacy_modal");
        $("#stream_privacy_modal").remove();
        return;
    }

    channel.patch({
        url: "/json/streams/" + stream_id,
        data,
        success() {
            overlays.close_modal("#stream_privacy_modal");
            $("#stream_privacy_modal").remove();
            // The rest will be done by update stream event we will get.
        },
        error(xhr) {
            ui_report.error(i18n.t("Failed"), xhr, stream_privacy_status);
            $("#change-stream-privacy-button").text(i18n.t("Try again"));
        },
    });
}

export function change_stream_name(e) {
    e.preventDefault();
    const sub_settings = $(e.target).closest(".subscription_settings");
    const stream_id = get_stream_id(e.target);
    const new_name_box = sub_settings.find(".stream-name-editable");
    const new_name = new_name_box.text().trim();
    const old_name = stream_data.maybe_get_stream_name(stream_id);

    $(".stream_change_property_info").hide();

    if (old_name === new_name) {
        return;
    }

    channel.patch({
        // Stream names might contain unsafe characters so we must encode it first.
        url: "/json/streams/" + stream_id,
        data: {new_name: JSON.stringify(new_name)},
        success() {
            new_name_box.val("");
            ui_report.success(
                i18n.t("The stream has been renamed!"),
                $(".stream_change_property_info"),
            );
        },
        error(xhr) {
            new_name_box.text(old_name);
            ui_report.error(i18n.t("Error"), xhr, $(".stream_change_property_info"));
        },
    });
}

export function set_raw_description(target, destination) {
    const sub = get_sub_for_target(target);
    if (!sub) {
        blueslip.error("set_raw_description() fails");
        return;
    }
    destination.text(sub.description);
}

export function change_stream_description(e) {
    e.preventDefault();

    const sub_settings = $(e.target).closest(".subscription_settings");
    const sub = get_sub_for_target(e.target);
    if (!sub) {
        blueslip.error("change_stream_description() fails");
        return;
    }

    const stream_id = sub.stream_id;
    const description = sub_settings.find(".stream-description-editable").text().trim();
    $(".stream_change_property_info").hide();

    if (description === sub.description) {
        sub_settings
            .find(".stream-description-editable")
            .html(util.clean_user_content_links(sub.rendered_description));
        return;
    }

    channel.patch({
        // Description might contain unsafe characters so we must encode it first.
        url: "/json/streams/" + stream_id,
        data: {
            description: JSON.stringify(description),
        },
        success() {
            // The event from the server will update the rest of the UI
            ui_report.success(
                i18n.t("The stream description has been updated!"),
                $(".stream_change_property_info"),
            );
        },
        error(xhr) {
            sub_settings
                .find(".stream-description-editable")
                .html(util.clean_user_content_links(sub.rendered_description));
            ui_report.error(i18n.t("Error"), xhr, $(".stream_change_property_info"));
        },
    });
}

export function archive_stream(stream_id, alert_element, stream_row) {
    channel.del({
        url: "/json/streams/" + stream_id,
        data: {
            is_archive: JSON.stringify(true),
        },
        error(xhr) {
            ui_report.error(i18n.t("Failed"), xhr, alert_element);
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

        subs.sub_or_unsub(sub);
    });

    $("#subscriptions_table").on("click", ".change-stream-privacy", (e) => {
        const stream_id = get_stream_id(e.target);
        const stream = stream_data.get_sub_by_id(stream_id);

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
            realm_message_retention_setting: get_display_text_for_realm_message_retention_setting(),
            upgrade_text_for_wide_organization_logo:
                page_params.upgrade_text_for_wide_organization_logo,
            is_stream_edit: true,
        };
        const change_privacy_modal = render_subscription_stream_privacy_modal(template_data);
        $("#stream_privacy_modal").remove();
        $("#subscriptions_table").append(change_privacy_modal);
        set_stream_message_retention_setting_dropdown(stream);
        overlays.open_modal("#stream_privacy_modal");
        e.preventDefault();
        e.stopPropagation();
    });

    $("#subscriptions_table").on("click", "#change-stream-privacy-button", change_stream_privacy);

    $("#subscriptions_table").on("click", ".close-privacy-modal", (e) => {
        // Re-enable background mouse events when we close the modal
        // via the "x" in the corner.  (The other modal-close code
        // paths call `overlays.close_modal`, rather than using
        // bootstrap's data-dismiss=modal feature, and this is done
        // there).
        //
        // TODO: It would probably be better to just do this
        // unconditionally inside the handler for the event sent by
        // bootstrap on closing a modal.
        overlays.enable_background_mouse_events();

        // This fixes a weird bug in which, subscription_settings hides
        // unexpectedly by clicking the cancel button in a modal on top of it.
        e.stopPropagation();
    });

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
        if (e.which === 13) {
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
        const stream_subscription_info_elem = $(".stream_subscription_info").expectOne();

        function removal_success(data) {
            if (data.removed.length > 0) {
                // Remove the user from the subscriber list.
                list_entry.remove();
                stream_subscription_info_elem.text(i18n.t("Unsubscribed successfully!"));
                // The rest of the work is done via the subscription -> remove event we will get
            } else {
                stream_subscription_info_elem.text(i18n.t("User is already not subscribed."));
            }
            stream_subscription_info_elem.addClass("text-success").removeClass("text-error");
        }

        function removal_failure() {
            stream_subscription_info_elem
                .text(i18n.t("Error removing user from this stream."))
                .addClass("text-error")
                .removeClass("text-success");
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
        subs.sub_or_unsub(sub, stream_row);

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
            ui_report.client_error(i18n.t("Invalid stream id"), $(".stream_change_property_info"));
            return;
        }
        const stream_name = stream_data.maybe_get_stream_name(stream_id);
        const deactivate_stream_modal = render_settings_deactivation_stream_modal({
            stream_name,
            stream_id,
        });
        $("#deactivation_stream_modal").remove();
        $("#subscriptions_table").append(deactivate_stream_modal);
        overlays.open_modal("#deactivation_stream_modal");
    });

    $("#subscriptions_table").on("click", "#do_deactivate_stream_button", (e) => {
        const stream_id = $(e.target).data("stream-id");
        overlays.close_modal("#deactivation_stream_modal");
        $("#deactivation_stream_modal").remove();
        if (!stream_id) {
            ui_report.client_error(i18n.t("Invalid stream id"), $(".stream_change_property_info"));
            return;
        }
        const row = $(".stream-row.active");
        archive_stream(stream_id, $(".stream_change_property_info"), row);
    });

    $("#subscriptions_table").on("hide.bs.modal", "#deactivation_stream_modal", () => {
        $("#deactivation_stream_modal").remove();
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
