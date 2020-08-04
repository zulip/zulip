"use strict";

const render_settings_deactivation_stream_modal = require("../templates/settings/deactivation_stream_modal.hbs");
const render_stream_member_list_entry = require("../templates/stream_member_list_entry.hbs");
const render_subscription_settings = require("../templates/subscription_settings.hbs");
const render_subscription_stream_privacy_modal = require("../templates/subscription_stream_privacy_modal.hbs");

const settings_config = require("./settings_config");
const settings_data = require("./settings_data");
const util = require("./util");

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

exports.setup_subscriptions_tab_hash = function (tab_key_value) {
    if (tab_key_value === "all-streams") {
        hashchange.update_browser_history("#streams/all");
    } else if (tab_key_value === "subscribed") {
        hashchange.update_browser_history("#streams/subscribed");
    } else {
        blueslip.debug("Unknown tab_key_value: " + tab_key_value);
    }
};

exports.settings_for_sub = function (sub) {
    return $(
        "#subscription_overlay .subscription_settings[data-stream-id='" + sub.stream_id + "']",
    );
};

exports.is_sub_settings_active = function (sub) {
    // This function return whether the provided given sub object is
    // currently being viewed/edited in the stream edit UI.  This is
    // used to determine whether we need to rerender the stream edit
    // UI when a sub object is modified by an event.
    const active_stream = subs.active_stream();
    if (active_stream !== undefined && active_stream.id === sub.stream_id) {
        return true;
    }
    return false;
};

exports.get_users_from_subscribers = function (subscribers) {
    return subscribers.map((user_id) => people.get_by_user_id(user_id));
};

exports.get_retention_policy_text_for_subscription_type = function (sub) {
    let message_retention_days = sub.message_retention_days;
    // If both this stream and the organization-level policy are to retain forever,
    // there's no need to comment on retention policies when describing the stream.
    if (
        page_params.realm_message_retention_days === settings_config.retain_message_forever &&
        (sub.message_retention_days === null ||
            sub.message_retention_days === settings_config.retain_message_forever)
    ) {
        return;
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
};

exports.get_display_text_for_realm_message_retention_setting = function () {
    const realm_message_retention_days = page_params.realm_message_retention_days;
    if (realm_message_retention_days === settings_config.retain_message_forever) {
        return i18n.t("(forever)");
    }
    return i18n.t("(__message_retention_days__ days)", {
        message_retention_days: realm_message_retention_days,
    });
};

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
    if (target.constructor !== jQuery) {
        target = $(target);
    }
    const row = target.closest(".stream-row, .subscription_settings");
    return parseInt(row.attr("data-stream-id"), 10);
}

function get_sub_for_target(target) {
    const stream_id = get_stream_id(target);
    if (!stream_id) {
        blueslip.error("Cannot find stream id for target");
        return;
    }

    const sub = stream_data.get_sub_by_id(stream_id);
    if (!sub) {
        blueslip.error("get_sub_for_target() failed id lookup: " + stream_id);
        return;
    }
    return sub;
}

exports.open_edit_panel_for_row = function (stream_row) {
    const sub = get_sub_for_target(stream_row);

    $(".stream-row.active").removeClass("active");
    subs.show_subs_pane.settings();
    $(stream_row).addClass("active");
    setup_subscriptions_stream_hash(sub);
    exports.show_settings_for(stream_row);
};

exports.open_edit_panel_empty = function () {
    const tab_key = $(subs.get_active_data().tabs[0]).attr("data-tab-key");
    $(".stream-row.active").removeClass("active");
    subs.show_subs_pane.nothing_selected();
    exports.setup_subscriptions_tab_hash(tab_key);
};

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
    return $('.subscription_settings[data-stream-id="' + stream_id_str + '"] .subscriber-list');
}

exports.update_stream_name = function (sub, new_name) {
    const sub_settings = exports.settings_for_sub(sub);
    sub_settings.find(".email-address").text(sub.email_address);
    sub_settings.find(".stream-name-editable").text(new_name);
};

exports.update_stream_description = function (sub) {
    const stream_settings = exports.settings_for_sub(sub);
    stream_settings.find("input.description").val(sub.description);
    stream_settings
        .find(".stream-description-editable")
        .html(util.clean_user_content_links(sub.rendered_description));
};

exports.invite_user_to_stream = function (user_ids, sub, success, failure) {
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
};

function submit_add_subscriber_form(e) {
    const settings_row = $(e.target).closest(".subscription_settings");
    const sub = get_sub_for_target(settings_row);
    if (!sub) {
        blueslip.error(".subscriber_list_add form submit fails");
        return;
    }

    const user_ids = user_pill.get_user_ids(exports.pill_widget);
    const stream_subscription_info_elem = $(".stream_subscription_info").expectOne();

    if (user_ids.length === 0) {
        stream_subscription_info_elem
            .text(i18n.t("No user to subscribe."))
            .addClass("text-error")
            .removeClass("text-success");
        return;
    }

    function invite_success(data) {
        exports.pill_widget.clear();
        if (!Object.entries(data.already_subscribed).length) {
            stream_subscription_info_elem.text(i18n.t("Subscribed successfully!"));
            // The rest of the work is done via the subscription -> add event we will get
        } else {
            stream_subscription_info_elem.text(i18n.t("User already subscribed."));
            const already_subscribed_users = Object.keys(data.already_subscribed).join(", ");
            stream_subscription_info_elem.text(
                i18n.t(" __already_subscribed_users__ are already subscribed.", {
                    already_subscribed_users,
                }),
            );
        }
        stream_subscription_info_elem.addClass("text-success").removeClass("text-error");
    }

    function invite_failure(xhr) {
        const error = JSON.parse(xhr.responseText);
        stream_subscription_info_elem
            .text(error.msg)
            .addClass("text-error")
            .removeClass("text-success");
    }

    exports.invite_user_to_stream(user_ids, sub, invite_success, invite_failure);
}

exports.remove_user_from_stream = function (user_id, sub, success, failure) {
    // TODO: use stream_id when backend supports it
    const stream_name = sub.name;
    return channel.del({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([stream_name]), principals: JSON.stringify([user_id])},
        success,
        error: failure,
    });
};

exports.sort_but_pin_current_user_on_top = function (users) {
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
};

function show_subscription_settings(sub_row) {
    const stream_id = sub_row.data("stream-id");
    const sub = stream_data.get_sub_by_id(stream_id);
    const sub_settings = exports.settings_for_sub(sub);

    const colorpicker = sub_settings.find(".colorpicker");
    const color = stream_data.get_color(sub.name);
    stream_color.set_colorpicker_color(colorpicker, color);
    stream_ui_updates.update_add_subscriptions_elements(sub);

    const container = $(
        "#subscription_overlay .subscription_settings[data-stream-id='" +
            stream_id +
            "'] .pill-container",
    );
    exports.pill_widget = input_pill.create({
        container,
        create_item_from_text: user_pill.create_item_from_email,
        get_text_from_item: user_pill.get_email_from_item,
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

    const users = exports.get_users_from_subscribers(sub.subscribers);
    exports.sort_but_pin_current_user_on_top(users);

    function get_users_for_subscriber_typeahead() {
        const potential_subscribers = stream_data.potential_subscribers(sub);
        return user_pill.filter_taken_users(potential_subscribers, exports.pill_widget);
    }

    list_render.create(list, users, {
        name: "stream_subscribers/" + stream_id,
        modifier(item) {
            return format_member_list_elem(item);
        },
        filter: {
            element: $("[data-stream-id='" + stream_id + "'] .search"),
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
            },
        },
        simplebar_container: $(".subscriber_list_container"),
    });

    const opts = {source: get_users_for_subscriber_typeahead};
    pill_typeahead.set_up(sub_settings.find(".input"), exports.pill_widget, opts);
}

exports.is_notification_setting = function (setting_label) {
    if (setting_label.includes("_notifications")) {
        return true;
    } else if (setting_label.includes("_notify")) {
        return true;
    }
    return false;
};

exports.stream_settings = function (sub) {
    const settings_labels = settings_config.general_notifications_table_labels.stream;
    const check_realm_setting = settings_config.all_notifications().show_push_notifications_tooltip;

    const settings = Object.keys(settings_labels).map((setting) => {
        const ret = {
            name: setting,
            label: settings_labels[setting],
            disabled_realm_setting: check_realm_setting[setting],
            is_disabled: check_realm_setting[setting],
            is_notification_setting: exports.is_notification_setting(setting),
        };
        if (exports.is_notification_setting(setting)) {
            ret.is_checked = sub[setting + "_display"] && !check_realm_setting[setting];
            ret.is_disabled = ret.is_disabled || sub.is_muted;
            return ret;
        }
        ret.is_checked = sub[setting] && !check_realm_setting[setting];
        return ret;
    });
    return settings;
};

exports.show_settings_for = function (node) {
    const stream_id = get_stream_id(node);
    const sub = stream_data.get_sub_by_id(stream_id);

    stream_data.update_calculated_fields(sub);
    const html = render_subscription_settings({
        sub,
        settings: exports.stream_settings(sub),
        stream_post_policy_values: stream_data.stream_post_policy_values,
        message_retention_text: exports.get_retention_policy_text_for_subscription_type(sub),
    });
    ui.get_content_element($(".subscriptions .right .settings")).html(html);

    const sub_settings = exports.settings_for_sub(sub);

    $(".nothing-selected").hide();

    sub_settings.addClass("show");

    show_subscription_settings(sub_settings);
};

function stream_is_muted_changed(e) {
    const sub = get_sub_for_target(e.target);
    if (!sub) {
        blueslip.error("stream_is_muted_changed() fails");
        return;
    }

    const sub_settings = exports.settings_for_sub(sub);
    const notification_checkboxes = sub_settings.find(".sub_notification_setting");

    subs.set_muted(sub, e.target.checked, `#stream_change_property_status${sub.stream_id}`);
    sub_settings.find(".mute-note").toggleClass("hide-mute-note", !sub.is_muted);
    notification_checkboxes.toggleClass("muted-sub", sub.is_muted);
    notification_checkboxes.find("input[type='checkbox']").prop("disabled", sub.is_muted);
}

exports.stream_setting_changed = function (e, from_notification_settings) {
    if (e.target.name === "is_muted") {
        return;
    }

    const sub = get_sub_for_target(e.target);
    const status_element = from_notification_settings
        ? $(e.target).closest(".subsection-parent").find(".alert-notification")
        : $("#stream_change_property_status" + sub.stream_id);
    const setting = e.target.name;
    if (!sub) {
        blueslip.error("undefined sub in stream_setting_changed()");
        return;
    }
    if (exports.is_notification_setting(setting) && sub[setting] === null) {
        if (setting === "wildcard_mentions_notify") {
            sub[setting] = page_params[setting];
        } else {
            sub[setting] = page_params["enable_stream_" + setting];
        }
    }
    exports.set_stream_property(sub, setting, e.target.checked, status_element);
};

exports.bulk_set_stream_property = function (sub_data, status_element) {
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
};

exports.set_stream_property = function (sub, property, value, status_element) {
    const sub_data = {stream_id: sub.stream_id, property, value};
    exports.bulk_set_stream_property([sub_data], status_element);
};

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

    const privacy_setting = $("#stream_privacy_modal input[name=privacy]:checked").val();
    const stream_post_policy = parseInt(
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
        message_retention_days = parseInt(
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
        error() {
            $("#change-stream-privacy-button").text(i18n.t("Try again"));
        },
    });
}

exports.change_stream_name = function (e) {
    e.preventDefault();
    const sub_settings = $(e.target).closest(".subscription_settings");
    const stream_id = get_stream_id(e.target);
    const new_name_box = sub_settings.find(".stream-name-editable");
    const new_name = new_name_box.text().trim();
    $(".stream_change_property_info").hide();

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
            new_name_box.text(stream_data.maybe_get_stream_name(stream_id));
            ui_report.error(i18n.t("Error"), xhr, $(".stream_change_property_info"));
        },
    });
};

exports.set_raw_description = function (target, destination) {
    const sub_settings = $(target).closest(".subscription_settings");
    const sub = get_sub_for_target(sub_settings);
    if (!sub) {
        blueslip.error("set_raw_description() fails");
        return;
    }
    destination.text(sub.description);
};

exports.change_stream_description = function (e) {
    e.preventDefault();

    const sub_settings = $(e.target).closest(".subscription_settings");
    const sub = get_sub_for_target(sub_settings);
    if (!sub) {
        blueslip.error("change_stream_description() fails");
        return;
    }

    const stream_id = sub.stream_id;
    const description = sub_settings.find(".stream-description-editable").text().trim();
    $(".stream_change_property_info").hide();

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
};

exports.delete_stream = function (stream_id, alert_element, stream_row) {
    channel.del({
        url: "/json/streams/" + stream_id,
        error(xhr) {
            ui_report.error(i18n.t("Failed"), xhr, alert_element);
        },
        success() {
            stream_row.remove();
        },
    });
};

exports.initialize = function () {
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
            realm_message_retention_setting: exports.get_display_text_for_realm_message_retention_setting(),
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
        exports.stream_setting_changed,
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
        const target_user_id = parseInt(list_entry.attr("data-subscriber-id"), 10);
        const settings_row = $(e.target).closest(".subscription_settings");

        const sub = get_sub_for_target(settings_row);
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

        exports.remove_user_from_stream(target_user_id, sub, removal_success, removal_failure);
    });

    // This handler isn't part of the normal edit interface; it's the convenient
    // checkmark in the subscriber list.
    $("#subscriptions_table").on("click", ".sub_unsub_button", (e) => {
        const sub = get_sub_for_target(e.target);
        // Makes sure we take the correct stream_row.
        const stream_row = $(
            "#subscriptions_table div.stream-row[data-stream-id='" + sub.stream_id + "']",
        );
        subs.sub_or_unsub(sub, stream_row);

        if (!sub.subscribed) {
            exports.open_edit_panel_for_row(stream_row);
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
            ui_report.message(
                i18n.t("Invalid stream id"),
                $(".stream_change_property_info"),
                "alert-error",
            );
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
            ui_report.message(
                i18n.t("Invalid stream id"),
                $(".stream_change_property_info"),
                "alert-error",
            );
            return;
        }
        const row = $(".stream-row.active");
        exports.delete_stream(stream_id, $(".stream_change_property_info"), row);
    });

    $("#subscriptions_table").on("hide.bs.modal", "#deactivation_stream_modal", () => {
        $("#deactivation_stream_modal").remove();
    });

    $("#subscriptions_table").on("click", ".stream-row", function (e) {
        if ($(e.target).closest(".check, .subscription_settings").length === 0) {
            exports.open_edit_panel_for_row(this);
        }
    });

    $("#subscriptions_table").on("change", ".stream_message_retention_setting", (e) => {
        const dropdown_value = e.target.value;
        change_stream_message_retention_days_block_display_property(dropdown_value);
    });
};

window.stream_edit = exports;
