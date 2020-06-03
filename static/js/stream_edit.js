const util = require("./util");
const render_settings_deactivation_stream_modal = require("../templates/settings/deactivation_stream_modal.hbs");
const render_stream_member_list_entry = require('../templates/stream_member_list_entry.hbs');
const render_subscription_settings = require('../templates/subscription_settings.hbs');
const render_subscription_stream_privacy_modal = require("../templates/subscription_stream_privacy_modal.hbs");
const settings_data = require("./settings_data");
const settings_config = require("./settings_config");

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
        hashchange.update_browser_history('#streams/all');
    } else if (tab_key_value === "subscribed") {
        hashchange.update_browser_history('#streams/subscribed');
    } else {
        blueslip.debug("Unknown tab_key_value: " + tab_key_value);
    }
};

exports.settings_for_sub = function (sub) {
    return $("#subscription_overlay .subscription_settings[data-stream-id='" + sub.stream_id + "']");
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
    return subscribers.map(function (user_id) {
        return people.get_by_user_id(user_id);
    });
};

function clear_edit_panel() {
    $(".display-type #add_new_stream_title").hide();
    $(".display-type #stream_settings_title, .right .settings").show();
    $(".stream-row.active").removeClass("active");
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
        blueslip.error('Cannot find stream id for target');
        return;
    }

    const sub = stream_data.get_sub_by_id(stream_id);
    if (!sub) {
        blueslip.error('get_sub_for_target() failed id lookup: ' + stream_id);
        return;
    }
    return sub;
}

exports.open_edit_panel_for_row = function (stream_row) {
    const sub = get_sub_for_target(stream_row);

    clear_edit_panel();
    subs.show_subs_pane.settings();
    $(stream_row).addClass("active");
    setup_subscriptions_stream_hash(sub);
    exports.show_settings_for(stream_row);
};

exports.open_edit_panel_empty = function () {
    const tab_key = subs.get_active_data().tab.attr("data-tab-key");
    clear_edit_panel();
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
    stream_settings.find('input.description').val(sub.description);
    stream_settings.find('.stream-description-editable').html(
        util.clean_user_content_links(sub.rendered_description)
    );
};

exports.invite_user_to_stream = function (user_ids, sub, success, failure) {
    // TODO: use stream_id when backend supports it
    const stream_name = sub.name;
    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([{name: stream_name}]),
               principals: JSON.stringify(user_ids)},
        success: success,
        error: failure,
    });
};

exports.remove_user_from_stream = function (user_id, sub, success, failure) {
    // TODO: use stream_id when backend supports it
    const stream_name = sub.name;
    return channel.del({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([stream_name]),
               principals: JSON.stringify([user_id])},
        success: success,
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

    const colorpicker = sub_settings.find('.colorpicker');
    const color = stream_data.get_color(sub.name);
    stream_color.set_colorpicker_color(colorpicker, color);
    stream_ui_updates.update_add_subscriptions_elements(sub);

    const container = $("#subscription_overlay .subscription_settings[data-stream-id='" + stream_id + "'] .pill-container");
    exports.pill_widget = input_pill.create({
        container: container,
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
        modifier: function (item) {
            return format_member_list_elem(item);
        },
        filter: {
            element: $("[data-stream-id='" + stream_id + "'] .search"),
            predicate: function (item, value) {
                const person = item;

                if (person) {
                    if (person.email.toLocaleLowerCase().includes(value) &&
                        settings_data.show_email()) {
                        return true;
                    }
                    return person.full_name.toLowerCase().includes(value);
                }
            },
        },
    });

    user_pill.set_up_typeahead_on_pills(sub_settings.find('.input'),
                                        exports.pill_widget,
                                        function () {},
                                        get_users_for_subscriber_typeahead);
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
        sub: sub,
        settings: exports.stream_settings(sub),
        stream_post_policy_values: stream_data.stream_post_policy_values,
    });
    ui.get_content_element($('.subscriptions .right .settings')).html(html);

    const sub_settings = exports.settings_for_sub(sub);

    $(".nothing-selected").hide();

    sub_settings.addClass("show");

    show_subscription_settings(sub_settings);
};

function stream_is_muted_clicked(e) {
    const sub = get_sub_for_target(e.target);
    if (!sub) {
        blueslip.error('stream_is_muted_clicked() fails');
        return;
    }

    const sub_settings = exports.settings_for_sub(sub);
    const notification_checkboxes = sub_settings.find(".sub_notification_setting");

    subs.toggle_home(sub, `#stream_change_property_status${sub.stream_id}`);

    if (!sub.is_muted) {
        sub_settings.find(".mute-note").addClass("hide-mute-note");
        notification_checkboxes.removeClass("muted-sub");
        notification_checkboxes.find("input[type='checkbox']").prop("disabled", false);
    } else {
        sub_settings.find(".mute-note").removeClass("hide-mute-note");
        notification_checkboxes.addClass("muted-sub");
        notification_checkboxes.find("input[type='checkbox']").attr("disabled", true);
    }
}

exports.stream_setting_clicked = function (e) {
    if (e.currentTarget.id === 'sub_is_muted_setting') {
        return;
    }

    const sub = get_sub_for_target(e.target);
    let checkbox = $(e.currentTarget).find('.sub_setting_control');
    let status_element = "#stream_change_property_status" + sub.stream_id;
    // sub data is being changed from the notification settings page.
    if (checkbox.length === 0) {
        checkbox = $(e.currentTarget);
        status_element = checkbox.closest('.subsection-parent').find('.alert-notification');
    }
    const setting = checkbox.attr('name');
    if (!sub) {
        blueslip.error('undefined sub in stream_setting_clicked()');
        return;
    }
    if (checkbox.prop('disabled')) {
        return false;
    }
    if (exports.is_notification_setting(setting) && sub[setting] === null) {
        if (setting === 'wildcard_mentions_notify') {
            sub[setting] = page_params[setting];
        } else {
            sub[setting] = page_params["enable_stream_" + setting];
        }
    }
    exports.set_stream_property(sub, setting, !sub[setting], status_element);
};

exports.bulk_set_stream_property = function (sub_data, status_element) {
    const url = '/json/users/me/subscriptions/properties';
    const data = {subscription_data: JSON.stringify(sub_data)};
    if (!status_element) {
        return channel.post({
            url: url,
            data: data,
            timeout: 10 * 1000,
        });
    }

    settings_ui.do_settings_change(channel.post, url, data, status_element);
};

exports.set_stream_property = function (sub, property, value, status_element) {
    const sub_data = {stream_id: sub.stream_id, property: property, value: value};
    exports.bulk_set_stream_property([sub_data], status_element);
};

function change_stream_privacy(e) {
    e.stopPropagation();

    const stream_id = $(e.target).data("stream-id");
    const sub = stream_data.get_sub_by_id(stream_id);

    const privacy_setting = $('#stream_privacy_modal input[name=privacy]:checked').val();
    const stream_post_policy = parseInt($('#stream_privacy_modal input[name=stream-post-policy]:checked').val(), 10);

    let invite_only;
    let history_public_to_subscribers;

    if (privacy_setting === 'invite-only') {
        invite_only = true;
        history_public_to_subscribers = false;
    } else if (privacy_setting === 'invite-only-public-history') {
        invite_only = true;
        history_public_to_subscribers = true;
    } else {
        invite_only = false;
        history_public_to_subscribers = true;
    }

    $(".stream_change_property_info").hide();
    const data = {
        stream_name: sub.name,
        // toggle the privacy setting
        is_private: JSON.stringify(invite_only),
        stream_post_policy: JSON.stringify(stream_post_policy),
        history_public_to_subscribers: JSON.stringify(history_public_to_subscribers),
    };

    channel.patch({
        url: "/json/streams/" + stream_id,
        data: data,
        success: function () {
            overlays.close_modal('#stream_privacy_modal');
            $("#stream_privacy_modal").remove();
            // The rest will be done by update stream event we will get.
        },
        error: function () {
            $("#change-stream-privacy-button").text(i18n.t("Try again"));
        },
    });
}

exports.change_stream_name = function (e) {
    e.preventDefault();
    const sub_settings = $(e.target).closest('.subscription_settings');
    const stream_id = get_stream_id(e.target);
    const new_name_box = sub_settings.find('.stream-name-editable');
    const new_name = $.trim(new_name_box.text());
    $(".stream_change_property_info").hide();

    channel.patch({
        // Stream names might contain unsafe characters so we must encode it first.
        url: "/json/streams/" + stream_id,
        data: {new_name: JSON.stringify(new_name)},
        success: function () {
            new_name_box.val('');
            ui_report.success(i18n.t("The stream has been renamed!"), $(".stream_change_property_info"));
        },
        error: function (xhr) {
            new_name_box.text(stream_data.maybe_get_stream_name(stream_id));
            ui_report.error(i18n.t("Error"), xhr, $(".stream_change_property_info"));
        },
    });
};

exports.set_raw_description = function (target, destination) {
    const sub_settings = $(target).closest('.subscription_settings');
    const sub = get_sub_for_target(sub_settings);
    if (!sub) {
        blueslip.error('set_raw_description() fails');
        return;
    }
    destination.text(sub.description);
};

exports.change_stream_description = function (e) {
    e.preventDefault();

    const sub_settings = $(e.target).closest('.subscription_settings');
    const sub = get_sub_for_target(sub_settings);
    if (!sub) {
        blueslip.error('change_stream_description() fails');
        return;
    }

    const stream_id = sub.stream_id;
    const description = sub_settings.find('.stream-description-editable').text().trim();
    $(".stream_change_property_info").hide();

    channel.patch({
        // Description might contain unsafe characters so we must encode it first.
        url: '/json/streams/' + stream_id,
        data: {
            description: JSON.stringify(description),
        },
        success: function () {
            // The event from the server will update the rest of the UI
            ui_report.success(i18n.t("The stream description has been updated!"),
                              $(".stream_change_property_info"));
        },
        error: function (xhr) {
            sub_settings.find('.stream-description-editable').html(
                util.clean_user_content_links(sub.rendered_description)
            );
            ui_report.error(i18n.t("Error"), xhr, $(".stream_change_property_info"));
        },
    });
};

exports.delete_stream = function (stream_id, alert_element, stream_row) {
    channel.del({
        url: '/json/streams/' + stream_id,
        error: function (xhr) {
            ui_report.error(i18n.t("Failed"), xhr, alert_element);
        },
        success: function () {
            stream_row.remove();
        },
    });
};

exports.initialize = function () {
    $("#main_div").on("click", ".stream_sub_unsub_button", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const stream_name = narrow_state.stream();
        if (stream_name === undefined) {
            return;
        }
        const sub = stream_data.get_sub(stream_name);
        subs.sub_or_unsub(sub);
    });

    $("#subscriptions_table").on("click", ".change-stream-privacy", function (e) {
        const stream_id = get_stream_id(e.target);
        const stream = stream_data.get_sub_by_id(stream_id);
        const template_data = {
            stream_id: stream_id,
            stream_name: stream.name,
            stream_post_policy_values: stream_data.stream_post_policy_values,
            stream_post_policy: stream.stream_post_policy,
            is_public: !stream.invite_only,
            is_private: stream.invite_only && !stream.history_public_to_subscribers,
            is_private_with_public_history: stream.invite_only &&
                stream.history_public_to_subscribers,
            is_admin: page_params.is_admin,
        };
        const change_privacy_modal = render_subscription_stream_privacy_modal(template_data);
        $("#stream_privacy_modal").remove();
        $("#subscriptions_table").append(change_privacy_modal);
        overlays.open_modal('#stream_privacy_modal');
        e.preventDefault();
        e.stopPropagation();
    });

    $("#subscriptions_table").on('click', '#change-stream-privacy-button',
                                 change_stream_privacy);

    $("#subscriptions_table").on('click', '.close-privacy-modal', function (e) {
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

    $("#subscriptions_table").on("click", "#sub_is_muted_setting",
                                 stream_is_muted_clicked);

    $("#subscriptions_table").on("click", ".sub_setting_checkbox",
                                 exports.stream_setting_clicked);

    $("#subscriptions_table").on("submit", ".subscriber_list_add form", function (e) {
        e.preventDefault();
        const settings_row = $(e.target).closest('.subscription_settings');
        const sub = get_sub_for_target(settings_row);
        if (!sub) {
            blueslip.error('.subscriber_list_add form submit fails');
            return;
        }

        const user_ids = user_pill.get_user_ids(exports.pill_widget);
        const stream_subscription_info_elem = $('.stream_subscription_info').expectOne();

        function invite_success(data) {
            exports.pill_widget.clear();
            if (!Object.entries(data.already_subscribed).length) {
                stream_subscription_info_elem.text(i18n.t("Subscribed successfully!"));
                // The rest of the work is done via the subscription -> add event we will get
            } else {
                stream_subscription_info_elem.text(i18n.t("User already subscribed."));
                const already_subscribed_users = Object.keys(data.already_subscribed).join(', ');
                stream_subscription_info_elem.text(i18n.t(
                    " __already_subscribed_users__ are already subscribed.", {already_subscribed_users: already_subscribed_users}));
            }
            stream_subscription_info_elem.addClass("text-success")
                .removeClass("text-error");
        }

        function invite_failure(xhr) {
            const error = JSON.parse(xhr.responseText);
            stream_subscription_info_elem.text(error.msg)
                .addClass("text-error").removeClass("text-success");
        }

        exports.invite_user_to_stream(user_ids, sub, invite_success, invite_failure);
    });

    $("#subscriptions_table").on("submit", ".subscriber_list_remove form", function (e) {
        e.preventDefault();

        const list_entry = $(e.target).closest("tr");
        const target_user_id = parseInt(list_entry.attr("data-subscriber-id"), 10);
        const settings_row = $(e.target).closest('.subscription_settings');

        const sub = get_sub_for_target(settings_row);
        if (!sub) {
            blueslip.error('.subscriber_list_remove form submit fails');
            return;
        }
        const stream_subscription_info_elem = $('.stream_subscription_info').expectOne();

        function removal_success(data) {
            if (data.removed.length > 0) {
                // Remove the user from the subscriber list.
                list_entry.remove();
                stream_subscription_info_elem.text(i18n.t("Unsubscribed successfully!"));
                // The rest of the work is done via the subscription -> remove event we will get
            } else {
                stream_subscription_info_elem.text(i18n.t("User is already not subscribed."));
            }
            stream_subscription_info_elem.addClass('text-success')
                .removeClass('text-error');
        }

        function removal_failure() {
            stream_subscription_info_elem.text(i18n.t("Error removing user from this stream."))
                .addClass("text-error").removeClass("text-success");
        }

        exports.remove_user_from_stream(target_user_id, sub, removal_success,
                                        removal_failure);
    });

    // This handler isn't part of the normal edit interface; it's the convenient
    // checkmark in the subscriber list.
    $("#subscriptions_table").on("click", ".sub_unsub_button", function (e) {
        const sub = get_sub_for_target(e.target);
        // Makes sure we take the correct stream_row.
        const stream_row = $("#subscriptions_table div.stream-row[data-stream-id='" + sub.stream_id + "']");
        subs.sub_or_unsub(sub, stream_row);

        if (!sub.subscribed) {
            exports.open_edit_panel_for_row(stream_row);
        }
        stream_ui_updates.update_regular_sub_settings(sub);

        e.preventDefault();
        e.stopPropagation();
    });

    $("#subscriptions_table").on("click", ".deactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const stream_id = get_stream_id(e.target);
        if (!stream_id) {
            ui_report.message(i18n.t("Invalid stream id"), $(".stream_change_property_info"), 'alert-error');
            return;
        }
        const stream_name = stream_data.maybe_get_stream_name(stream_id);
        const deactivate_stream_modal = render_settings_deactivation_stream_modal({
            stream_name: stream_name,
            stream_id: stream_id,
        });
        $("#deactivation_stream_modal").remove();
        $("#subscriptions_table").append(deactivate_stream_modal);
        overlays.open_modal('#deactivation_stream_modal');
    });

    $("#subscriptions_table").on("click", "#do_deactivate_stream_button", function (e) {
        const stream_id = $(e.target).data("stream-id");
        overlays.close_modal('#deactivation_stream_modal');
        $("#deactivation_stream_modal").remove();
        if (!stream_id) {
            ui_report.message(i18n.t("Invalid stream id"), $(".stream_change_property_info"), 'alert-error');
            return;
        }
        const row = $(".stream-row.active");
        exports.delete_stream(stream_id, $(".stream_change_property_info"), row);
    });

    $("#subscriptions_table").on("hide.bs.modal", "#deactivation_stream_modal", function () {
        $("#deactivation_stream_modal").remove();
    });

    $("#subscriptions_table").on("click", ".stream-row", function (e) {
        if ($(e.target).closest(".check, .subscription_settings").length === 0) {
            exports.open_edit_panel_for_row(this);
        }
    });

    $(document).on('peer_subscribe.zulip peer_unsubscribe.zulip', function (e, data) {
        const sub = stream_data.get_sub(data.stream_name);
        subs.rerender_subscriptions_settings(sub);
    });
};

window.stream_edit = exports;
