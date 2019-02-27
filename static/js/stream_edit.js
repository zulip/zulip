var stream_edit = (function () {

var exports = {};

function setup_subscriptions_stream_hash(sub) {
    var hash = hash_util.stream_edit_uri(sub);
    hashchange.update_browser_history(hash);
}

function settings_for_sub(sub) {
    var id = parseInt(sub.stream_id, 10);
    return $("#subscription_overlay .subscription_settings[data-stream-id='" + id + "']");
}

exports.is_sub_settings_active = function (sub) {
    // This function return whether the provided given sub object is
    // currently being viewed/edited in the stream edit UI.  This is
    // used to determine whether we need to rerender the stream edit
    // UI when a sub object is modified by an event.
    var active_stream = subs.active_stream();
    if (active_stream !== undefined && active_stream.id === sub.stream_id) {
        return true;
    }
    return false;
};

function get_email_of_subscribers(subscribers) {
    var emails = [];
    subscribers.each(function (o, i) {
        var email = people.get_person_from_user_id(i).email;
        emails.push(email);
    });
    return emails;
}

exports.rerender_subscribers_list = function (sub) {
    if (!sub.can_access_subscribers) {
        $(".subscriber_list_settings_container").hide();
    } else {
        var emails = get_email_of_subscribers(sub.subscribers);
        var subscribers_list = list_render.get("stream_subscribers/" + sub.stream_id);

        // Changing the data clears the rendered list and the list needs to be re-rendered.
        // Perform re-rendering only when the stream settings form of the corresponding
        // stream is open.
        if (subscribers_list) {
            exports.sort_but_pin_current_user_on_top(emails);
            subscribers_list.data(emails);
            subscribers_list.render();
            ui.update_scrollbar($(".subscriber_list_container"));
        }
        $(".subscriber_list_settings_container").show();
    }
};

exports.hide_sub_settings = function (sub) {
    var $settings = $(".subscription_settings[data-stream-id='" + sub.stream_id + "']");
    $settings.find(".regular_subscription_settings").removeClass('in');
    // Clear email address widget
    $settings.find(".email-address").html("");
    if (!sub.can_change_stream_permissions) {
        $settings.find(".change-stream-privacy").hide();
    }
};

exports.show_sub_settings = function (sub) {
    if (!exports.is_sub_settings_active(sub)) {
        return;
    }
    var $settings = $(".subscription_settings[data-stream-id='" + sub.stream_id + "']");
    if ($settings.find(".email-address").val().length === 0) {
        // Rerender stream email address, if not.
        $settings.find(".email-address").text(sub.email_address);
        $settings.find(".stream-email-box").show();
    }
    $settings.find(".regular_subscription_settings").addClass('in');
};

function clear_edit_panel() {
    $(".display-type #add_new_stream_title").hide();
    $(".display-type #stream_settings_title, .right .settings").show();
    $(".stream-row.active").removeClass("active");
}

exports.open_edit_panel_for_row = function (stream_row) {
    clear_edit_panel();
    subs.show_subs_pane.settings();
    $(stream_row).addClass("active");
    stream_edit.show_settings_for(stream_row);
};

exports.open_edit_panel_empty = function () {
    clear_edit_panel();
    subs.show_subs_pane.nothing_selected();
};

function format_member_list_elem(email) {
    var person = people.get_by_email(email);
    return templates.render('stream_member_list_entry',
                            {name: person.full_name, email: email,
                             displaying_for_admin: page_params.is_admin});
}

function get_subscriber_list(sub_row) {
    var id = sub_row.data("stream-id");
    return $('.subscription_settings[data-stream-id="' + id + '"] .subscriber-list');
}

exports.update_stream_name = function (sub, new_name) {
    var sub_settings = settings_for_sub(sub);
    sub_settings.find(".email-address").text(sub.email_address);
    sub_settings.find(".stream-name-editable").text(new_name);
};

exports.update_stream_description = function (sub) {
    var stream_settings = settings_for_sub(sub);
    stream_settings.find('input.description').val(sub.description);
    stream_settings.find('.stream-description-editable').html(sub.rendered_description);
};

exports.invite_user_to_stream = function (user_email, sub, success, failure) {
    // TODO: use stream_id when backend supports it
    var stream_name = sub.name;
    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([{name: stream_name}]),
               principals: JSON.stringify([user_email])},
        success: success,
        error: failure,
    });
};

exports.remove_user_from_stream = function (user_email, sub, success, failure) {
    // TODO: use stream_id when backend supports it
    var stream_name = sub.name;
    return channel.del({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([stream_name]),
               principals: JSON.stringify([user_email])},
        success: success,
        error: failure,
    });
};

function get_stream_id(target) {
    if (target.constructor !== jQuery) {
        target = $(target);
    }
    return target.closest(".stream-row, .subscription_settings").attr("data-stream-id");
}


function get_sub_for_target(target) {
    var stream_id = get_stream_id(target);
    if (!stream_id) {
        blueslip.error('Cannot find stream id for target');
        return;
    }

    var sub = stream_data.get_sub_by_id(stream_id);
    if (!sub) {
        blueslip.error('get_sub_for_target() failed id lookup: ' + stream_id);
        return;
    }
    return sub;
}

exports.sort_but_pin_current_user_on_top = function (emails) {
    if (emails === undefined) {
        blueslip.error("Undefined emails are passed to function sort_but_pin_current_user_on_top");
        return;
    }
    // Set current user top of subscription list, if subscribed.
    if (emails.indexOf(people.my_current_email()) > -1) {
        emails.splice(emails.indexOf(people.my_current_email()), 1);
        emails.sort();
        emails.unshift(people.my_current_email());
    } else {
        emails.sort();
    }
};

function show_subscription_settings(sub_row) {
    var stream_id = sub_row.data("stream-id");
    var sub = stream_data.get_sub_by_id(stream_id);
    var sub_settings = settings_for_sub(sub);

    var colorpicker = sub_settings.find('.colorpicker');
    var color = stream_data.get_color(sub.name);
    stream_color.set_colorpicker_color(colorpicker, color);
    subs.update_add_subscriptions_elements(sub.can_add_subscribers);

    if (!sub.render_subscribers) {
        return;
    }
    // fetch subscriber list from memory.
    var list = get_subscriber_list(sub_settings);
    list.empty();

    var emails = get_email_of_subscribers(sub.subscribers);
    exports.sort_but_pin_current_user_on_top(emails);

    list_render.create(list, emails, {
        name: "stream_subscribers/" + stream_id,
        modifier: function (item) {
            return format_member_list_elem(item);
        },
        filter: {
            element: $("[data-stream-id='" + stream_id + "'] .search"),
            callback: function (item, value) {
                var person = people.get_by_email(item);

                if (person) {
                    var email = person.email.toLocaleLowerCase();
                    var full_name = person.full_name.toLowerCase();

                    return email.indexOf(value) > -1 || full_name.indexOf(value) > -1;
                }
            },
        },
    }).init();

    ui.set_up_scrollbar($(".subscriber_list_container"));

    sub_settings.find('input[name="principal"]').typeahead({
        source: people.get_realm_persons, // This is a function.
        items: 5,
        highlighter: function (item) {
            return typeahead_helper.render_person(item);
        },
        matcher: function (item) {
            var query = $.trim(this.query.toLowerCase());
            if (query === '' || query === item.email) {
                return false;
            }
            // Case-insensitive.
            var item_matches = item.email.toLowerCase().indexOf(query) !== -1 ||
                               item.full_name.toLowerCase().indexOf(query) !== -1;
            var is_subscribed = stream_data.is_user_subscribed(sub.name, item.user_id);
            return item_matches && !is_subscribed;
        },
        sorter: function (matches) {
            var current_stream = compose_state.stream_name();
            return typeahead_helper.sort_recipientbox_typeahead(
                this.query, matches, current_stream);
        },
        updater: function (item) {
            return item.email;
        },
    });
}

exports.show_settings_for = function (node) {
    var stream_id = get_stream_id(node);
    var sub = stream_data.get_sub_by_id(stream_id);

    stream_data.update_calculated_fields(sub);
    var html = templates.render('subscription_settings', sub);
    $('.subscriptions .right .settings').html(html);

    var sub_settings = settings_for_sub(sub);

    $(".nothing-selected").hide();

    ui.update_scrollbar($("#subscription_overlay .settings"));

    sub_settings.addClass("show");

    show_subscription_settings(sub_settings);
};

function stream_home_view_clicked(e) {
    var sub = get_sub_for_target(e.target);
    if (!sub) {
        blueslip.error('stream_home_view_clicked() fails');
        return;
    }

    var sub_settings = settings_for_sub(sub);
    var notification_checkboxes = sub_settings.find(".sub_notification_setting");

    subs.toggle_home(sub);

    if (sub.in_home_view) {
        sub_settings.find(".mute-note").addClass("hide-mute-note");
        notification_checkboxes.removeClass("muted-sub");
        notification_checkboxes.find("input[type='checkbox']").prop("disabled", false);
    } else {
        sub_settings.find(".mute-note").removeClass("hide-mute-note");
        notification_checkboxes.addClass("muted-sub");
        notification_checkboxes.find("input[type='checkbox']").attr("disabled", true);
    }
}

exports.bulk_set_stream_property = function (sub_data) {
    return channel.post({
        url: '/json/users/me/subscriptions/properties',
        data: {subscription_data: JSON.stringify(sub_data)},
        timeout: 10 * 1000,
    });
};

exports.set_stream_property = function (sub, property, value) {
    var sub_data = {stream_id: sub.stream_id, property: property, value: value};
    exports.bulk_set_stream_property([sub_data]);
};

exports.set_notification_setting_for_all_streams = function (notification_type, new_setting) {
    var sub_data = [];
    _.each(stream_data.subscribed_subs(), function (sub) {
        if (sub[notification_type] !== new_setting) {
            sub_data.push({
                stream_id: sub.stream_id,
                property: notification_type,
                value: new_setting,
            });
        }
    });
    exports.bulk_set_stream_property(sub_data);
};

function redraw_privacy_related_stuff(sub_row, sub) {
    var stream_settings = settings_for_sub(sub);
    var html;

    stream_data.update_calculated_fields(sub);

    html = templates.render('subscription_setting_icon', sub);
    sub_row.find('.icon').expectOne().replaceWith($(html));

    html = templates.render('subscription_type', sub);
    stream_settings.find('.subscription-type-text').expectOne().html(html);

    if (sub.invite_only) {
        stream_settings.find(".large-icon")
            .removeClass("hash").addClass("lock")
            .html("<i class='fa fa-lock' aria-hidden='true'></i>");
    } else {
        stream_settings.find(".large-icon")
            .addClass("hash").removeClass("lock")
            .html("");
    }

    stream_list.redraw_stream_privacy(sub);
}

function change_stream_privacy(e) {
    e.stopPropagation();

    var stream_id = $(e.target).data("stream-id");
    var sub = stream_data.get_sub_by_id(stream_id);

    var privacy_setting = $('#stream_privacy_modal input[name=privacy]:checked').val();
    var is_announcement_only = $('#stream_privacy_modal input[name=is-announcement-only]').prop('checked');

    var invite_only;
    var history_public_to_subscribers;

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
    var data = {
        stream_name: sub.name,
        // toggle the privacy setting
        is_private: JSON.stringify(invite_only),
        is_announcement_only: JSON.stringify(is_announcement_only),
        history_public_to_subscribers: JSON.stringify(history_public_to_subscribers),
    };

    channel.patch({
        url: "/json/streams/" + stream_id,
        data: data,
        success: function () {
            sub = stream_data.get_sub_by_id(stream_id);
            var sub_row = $(".stream-row[data-stream-id='" + stream_id + "']");

            // save new privacy settings.
            sub.invite_only = invite_only;
            sub.is_announcement_only = is_announcement_only;
            sub.history_public_to_subscribers = history_public_to_subscribers;

            redraw_privacy_related_stuff(sub_row, sub);
            $("#stream_privacy_modal").remove();

            // For auto update, without rendering whole template
            stream_data.update_calculated_fields(sub);
            if (!sub.can_change_stream_permissions) {
                $(".change-stream-privacy").hide();
            }
        },
        error: function () {
            $("#change-stream-privacy-button").text(i18n.t("Try again"));
        },
    });
}

function stream_desktop_notifications_clicked(e) {
    var sub = get_sub_for_target(e.target);
    sub.desktop_notifications = !sub.desktop_notifications;
    exports.set_stream_property(sub, 'desktop_notifications', sub.desktop_notifications);
}

function stream_audible_notifications_clicked(e) {
    var sub = get_sub_for_target(e.target);
    sub.audible_notifications = !sub.audible_notifications;
    exports.set_stream_property(sub, 'audible_notifications', sub.audible_notifications);
}

function stream_push_notifications_clicked(e) {
    var sub = get_sub_for_target(e.target);
    sub.push_notifications = !sub.push_notifications;
    exports.set_stream_property(sub, 'push_notifications', sub.push_notifications);
}

function stream_email_notifications_clicked(e) {
    var sub = get_sub_for_target(e.target);
    sub.email_notifications = !sub.email_notifications;
    exports.set_stream_property(sub, 'email_notifications', sub.email_notifications);
}

function stream_pin_clicked(e) {
    var sub = get_sub_for_target(e.target);
    if (!sub) {
        blueslip.error('stream_pin_clicked() fails');
        return;
    }
    subs.toggle_pin_to_top_stream(sub);
}

exports.change_stream_name = function (e) {
    e.preventDefault();
    var sub_settings = $(e.target).closest('.subscription_settings');
    var stream_id = $(e.target).closest(".subscription_settings").attr("data-stream-id");
    var new_name_box = sub_settings.find('.stream-name-editable');
    var new_name = $.trim(new_name_box.text());
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
            ui.update_scrollbar($("#subscription_overlay .settings"));
        },
    });
};

exports.set_raw_description = function (target, destination) {
    var sub_settings = $(target).closest('.subscription_settings');
    var sub = get_sub_for_target(sub_settings);
    if (!sub) {
        blueslip.error('set_raw_description() fails');
        return;
    }
    destination.text(sub.description);
};

exports.change_stream_description = function (e) {
    e.preventDefault();

    var sub_settings = $(e.target).closest('.subscription_settings');
    var sub = get_sub_for_target(sub_settings);
    if (!sub) {
        blueslip.error('change_stream_description() fails');
        return;
    }

    var stream_id = sub.stream_id;
    var description = sub_settings.find('.stream-description-editable').text().trim();
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
            sub_settings.find('.stream-description-editable').html(sub.rendered_description);
            ui_report.error(i18n.t("Error"), xhr, $(".stream_change_property_info"));
            ui.update_scrollbar($("#subscription_overlay .settings"));
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

        var stream_name = narrow_state.stream();
        if (stream_name === undefined) {
            return;
        }
        var sub = stream_data.get_sub(stream_name);
        subs.sub_or_unsub(sub);
    });

    $("#subscriptions_table").on("click", ".change-stream-privacy", function (e) {
        var stream_id = get_stream_id(e.target);
        var stream = stream_data.get_sub_by_id(stream_id);
        var template_data = {
            stream_id: stream_id,
            stream_name: stream.name,
            is_announcement_only: stream.is_announcement_only,
            is_public: !stream.invite_only,
            is_private: stream.invite_only && !stream.history_public_to_subscribers,
            is_private_with_public_history: stream.invite_only &&
                stream.history_public_to_subscribers,
            is_admin: page_params.is_admin,
        };
        var change_privacy_modal = templates.render("subscription_stream_privacy_modal", template_data);
        $("#stream_privacy_modal").remove();
        $("#subscriptions_table").append(change_privacy_modal);
        overlays.open_modal('stream_privacy_modal');
    });

    $("#subscriptions_table").on('click', '#change-stream-privacy-button',
                                 change_stream_privacy);

    $("#subscriptions_table").on('click', '.close-privacy-modal', function (e) {
        // This fixes a weird bug in which, subscription_settings hides
        // unexpectedly by clicking the cancel button.
        e.stopPropagation();
    });

    $("#subscriptions_table").on("click", "#sub_setting_not_in_home_view",
                                 stream_home_view_clicked);
    $("#subscriptions_table").on("click", "#sub_desktop_notifications_setting",
                                 stream_desktop_notifications_clicked);
    $("#subscriptions_table").on("click", "#sub_audible_notifications_setting",
                                 stream_audible_notifications_clicked);
    $("#subscriptions_table").on("click", "#sub_push_notifications_setting",
                                 stream_push_notifications_clicked);
    $("#subscriptions_table").on("click", "#sub_email_notifications_setting",
                                 stream_email_notifications_clicked);
    $("#subscriptions_table").on("click", "#sub_pin_setting",
                                 stream_pin_clicked);

    $("#subscriptions_table").on("submit", ".subscriber_list_add form", function (e) {
        e.preventDefault();
        var settings_row = $(e.target).closest('.subscription_settings');
        var sub = get_sub_for_target(settings_row);
        if (!sub) {
            blueslip.error('.subscriber_list_add form submit fails');
            return;
        }

        var text_box = settings_row.find('input[name="principal"]');
        var principal = $.trim(text_box.val());
        var stream_subscription_info_elem = $('.stream_subscription_info').expectOne();

        function invite_success(data) {
            text_box.val('');

            if (data.subscribed.hasOwnProperty(principal)) {
                stream_subscription_info_elem.text(i18n.t("Subscribed successfully!"));
                // The rest of the work is done via the subscription -> add event we will get
            } else {
                stream_subscription_info_elem.text(i18n.t("User already subscribed."));
            }
            stream_subscription_info_elem.addClass("text-success")
                .removeClass("text-error");
        }

        function invite_failure(xhr) {
            var error = JSON.parse(xhr.responseText);
            stream_subscription_info_elem.text(error.msg)
                .addClass("text-error").removeClass("text-success");
        }

        exports.invite_user_to_stream(principal, sub, invite_success, invite_failure);
    });

    $("#subscriptions_table").on("submit", ".subscriber_list_remove form", function (e) {
        e.preventDefault();

        var list_entry = $(e.target).closest("tr");
        var principal = list_entry.children(".subscriber-email").text();
        var settings_row = $(e.target).closest('.subscription_settings');

        var sub = get_sub_for_target(settings_row);
        if (!sub) {
            blueslip.error('.subscriber_list_remove form submit fails');
            return;
        }
        var stream_subscription_info_elem = $('.stream_subscription_info').expectOne();

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
            ui.update_scrollbar($("#subscription_overlay .settings"));
        }

        function removal_failure() {
            stream_subscription_info_elem.text(i18n.t("Error removing user from this stream."))
                .addClass("text-error").removeClass("text-success");
        }

        exports.remove_user_from_stream(principal, sub, removal_success,
                                        removal_failure);
    });

    // This handler isn't part of the normal edit interface; it's the convenient
    // checkmark in the subscriber list.
    $("#subscriptions_table").on("click", ".sub_unsub_button", function (e) {
        var sub = get_sub_for_target(e.target);
        var stream_row = $(this).parent();
        subs.sub_or_unsub(sub);
        var sub_settings = settings_for_sub(sub);
        var regular_sub_settings = sub_settings.find(".regular_subscription_settings");
        if (!sub.subscribed) {
            regular_sub_settings.addClass("in");
            exports.open_edit_panel_for_row(stream_row);
        } else {
            regular_sub_settings.removeClass("in");
        }

        setup_subscriptions_stream_hash(sub);
        e.preventDefault();
        e.stopPropagation();
    });

    $("#subscriptions_table").on("click", ".deactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var stream_id = get_stream_id(e.target);
        if (!stream_id) {
            ui_report.message(i18n.t("Invalid stream id"), $(".stream_change_property_info"), 'alert-error');
            return;
        }
        var stream_name = stream_data.maybe_get_stream_name(stream_id);
        var deactivate_stream_modal = templates.render("deactivation-stream-modal", {stream_name: stream_name});
        $(".subscription_settings").append(deactivate_stream_modal);
        overlays.open_modal('deactivation_stream_modal');
    });

    $("#subscriptions_table").on("click", "#do_deactivate_stream_button", function (e) {
        var stream_id = get_stream_id(e.target);
        overlays.close_modal('deactivation_stream_modal');
        $("#deactivation_stream_modal").remove();
        if (!stream_id) {
            ui_report.message(i18n.t("Invalid stream id"), $(".stream_change_property_info"), 'alert-error');
            return;
        }
        var row = $(".stream-row.active");
        exports.delete_stream(stream_id, $(".stream_change_property_info"), row);
    });

    $("#subscriptions_table").on("hide.bs.modal", "#deactivation_stream_modal", function () {
        $("#deactivation_stream_modal").remove();
    });

    $("#subscriptions_table").on("click", ".stream-row", function (e) {
        if ($(e.target).closest(".check, .subscription_settings").length === 0) {
            exports.open_edit_panel_for_row(this);
            var stream_id = $(this).attr("data-stream-id");
            var sub = stream_data.get_sub_by_id(stream_id);
            setup_subscriptions_stream_hash(sub);
        }
    });

    $(document).on('peer_subscribe.zulip', function (e, data) {
        var sub = stream_data.get_sub(data.stream_name);
        subs.rerender_subscriptions_settings(sub);
    });

    $(document).on('peer_unsubscribe.zulip', function (e, data) {
        var sub = stream_data.get_sub(data.stream_name);
        subs.rerender_subscriptions_settings(sub);
    });

};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = stream_edit;
}
window.stream_edit = stream_edit;
