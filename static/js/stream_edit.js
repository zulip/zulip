var stream_edit = (function () {

var exports = {};

function setup_subscriptions_stream_hash(sub, stream_id) {
    subs.change_state.prevent_once();
    window.location.hash = "#streams" + "/" +
        stream_id + "/" +
        hash_util.encodeHashComponent(sub.name);
}

function settings_for_sub(sub) {
    var id = parseInt(sub.stream_id, 10);
    return $("#subscription_overlay .subscription_settings[data-stream-id='" + id + "']");
}

function get_email_of_subscribers(subscribers) {
    var emails = [];
    subscribers.each(function (o, i) {
        var email = people.get_person_from_user_id(i).email;
        emails.push(email);
    });
    return emails;
}

function rerender_subscribers_list(sub) {
    var emails = get_email_of_subscribers(sub.subscribers);
    var subscribers_list = list_render.get("stream_subscribers/" + sub.stream_id);

    // Changing the data clears the rendered list and the list needs to be re-rendered.
    // Perform re-rendering only when the stream settings form of the corresponding
    // stream is open.
    if (subscribers_list) {
        subscribers_list.data(emails);
        subscribers_list.render();
        ui.update_scrollbar($(".subscriber_list_container"));
    }
}

exports.collapse = function (sub) {
    // I am not sure whether this code is really correct; it was extracted
    // from subs.update_settings_for_unsubscribed() and possibly pre-dates
    // our big streams re-design in late 2016.
    var stream_settings = settings_for_sub(sub);
    if (stream_settings.hasClass('in')) {
        stream_settings.collapse('hide');
    }

    var sub_row = stream_settings.closest('.stream-row');
    sub_row.find(".regular_subscription_settings").removeClass('in');
};

exports.show_sub = function (sub) {
    var stream_settings = settings_for_sub(sub);
    var sub_row = stream_settings.closest('.stream-row');
    sub_row.find(".regular_subscription_settings").addClass('in');
};

exports.add_me_to_member_list = function (sub) {
    // Add the user to the member list if they're currently
    // viewing the members of this stream
    var stream_settings = settings_for_sub(sub);
    if (sub.render_subscribers && stream_settings.hasClass('in')) {
        exports.prepend_subscriber(
            stream_settings,
            people.my_current_email());
    }
};

exports.show_stream_row = function (node, show_settings) {
    $(".display-type #add_new_stream_title").hide();
    $(".display-type #stream_settings_title, .right .settings").show();
    $(".stream-row.active").removeClass("active");
    if (show_settings) {
        subs.show_subs_pane.settings();

        $(node).addClass("active");
        stream_edit.show_settings_for(node);
    } else {
        subs.show_subs_pane.nothing_selected();
    }
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

exports.prepend_subscriber = function (sub_row, email) {
    var list = get_subscriber_list(sub_row);
    list.prepend(format_member_list_elem(email));
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

function show_subscription_settings(sub_row) {
    var stream_id = sub_row.data("stream-id");
    var sub = stream_data.get_sub_by_id(stream_id);
    var sub_settings = settings_for_sub(sub);
    var alerts = sub_settings
        .find('.subscriber_list_container')
        .find('.alert-warning, .alert-error');

    var colorpicker = sub_settings.find('.colorpicker');
    var color = stream_data.get_color(sub.name);
    stream_color.set_colorpicker_color(colorpicker, color);

    if (!sub.render_subscribers) {
        return;
    }
    // fetch subscriber list from memory.
    var list = get_subscriber_list(sub_settings);
    alerts.addClass("hide");
    list.empty();

    var emails = get_email_of_subscribers(sub.subscribers);

    list_render(list, emails.sort(), {
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

                    return (email.indexOf(value) > -1 || full_name.indexOf(value) > -1);
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
            var item_matches = (item.email.toLowerCase().indexOf(query) !== -1) ||
                               (item.full_name.toLowerCase().indexOf(query) !== -1);
            var is_subscribed = stream_data.user_is_subscribed(sub.name, item.email);
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

exports.set_stream_property = function (sub, property, value) {
    // TODO: Fix backend so it takes a stream id.
    var sub_data = {stream_id: sub.stream_id, property: property, value: value};
    return channel.post({
        url: '/json/users/me/subscriptions/properties',
        data: {subscription_data: JSON.stringify([sub_data])},
        timeout:  10*1000,
    });
};

exports.set_notification_setting_for_all_streams = function (notification_type, new_setting) {
    _.each(stream_data.subscribed_subs(), function (sub) {
        if (sub[notification_type] !== new_setting) {
            exports.set_stream_property(sub, notification_type, new_setting);
        }
    });
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
            .html("<i class='icon-vector-lock'></i>");
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

    $("#subscriptions-status").hide();
    var data = {
        stream_name: sub.name,
        // toggle the privacy setting
        is_private: !sub.invite_only,
    };

    channel.patch({
        url: "/json/streams/" + stream_id,
        data: data,
        success: function () {
            sub = stream_data.get_sub_by_id(stream_id);
            var sub_row = $(".stream-row[data-stream-id='" + stream_id + "']");

            // save new privacy settings.
            sub.invite_only = !sub.invite_only;

            redraw_privacy_related_stuff(sub_row, sub);
            $("#stream_privacy_modal").remove();
        },
        error: function () {
            $("#change-stream-privacy-button").text(i18n.t("Try again"));
        },
    });
}

function stream_desktop_notifications_clicked(e) {
    var sub = get_sub_for_target(e.target);
    sub.desktop_notifications = ! sub.desktop_notifications;
    exports.set_stream_property(sub, 'desktop_notifications', sub.desktop_notifications);
}

function stream_audible_notifications_clicked(e) {
    var sub = get_sub_for_target(e.target);
    sub.audible_notifications = ! sub.audible_notifications;
    exports.set_stream_property(sub, 'audible_notifications', sub.audible_notifications);
}

function stream_push_notifications_clicked(e) {
    var sub = get_sub_for_target(e.target);
    sub.push_notifications = ! sub.push_notifications;
    exports.set_stream_property(sub, 'push_notifications', sub.push_notifications);
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

    $("#subscriptions-status").hide();

    channel.patch({
        // Stream names might contain unsafe characters so we must encode it first.
        url: "/json/streams/" + stream_id,
        data: {new_name: JSON.stringify(new_name)},
        success: function () {
            new_name_box.val('');
            ui_report.success(i18n.t("The stream has been renamed!"), $("#subscriptions-status "),
                              'subscriptions-status');
        },
        error: function (xhr) {
            ui_report.error(i18n.t("Error renaming stream"), xhr,
                            $("#subscriptions-status"), 'subscriptions-status');
        },
    });
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

    $('#subscriptions-status').hide();

    channel.patch({
        // Stream names might contain unsafe characters so we must encode it first.
        url: '/json/streams/' + stream_id,
        data: {
            description: JSON.stringify(description),
        },
        success: function () {
            // The event from the server will update the rest of the UI
            ui_report.success(i18n.t("The stream description has been updated!"),
                             $("#subscriptions-status"), 'subscriptions-status');
        },
        error: function (xhr) {
            ui_report.error(i18n.t("Error updating the stream description"), xhr,
                            $("#subscriptions-status"), 'subscriptions-status');
        },
    });
};

$(function () {
    $("#zfilt").on("click", ".stream_sub_unsub_button", function (e) {
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
            is_private: stream.can_make_public,
            stream_id: stream_id,
        };
        var change_privacy_modal = templates.render("subscription_stream_privacy_modal", template_data);

        $("#subscriptions_table").append(change_privacy_modal);

        $("#change-stream-privacy-button").click(function (e) {
            change_stream_privacy(e);
        });
    });

    $("#subscriptions_table").on("click", ".close-privacy-modal", function () {
        $("#stream_privacy_modal").remove();
    });

    $("#subscriptions_table").on("click", "#sub_setting_not_in_home_view",
                                 stream_home_view_clicked);
    $("#subscriptions_table").on("click", "#sub_desktop_notifications_setting",
                                 stream_desktop_notifications_clicked);
    $("#subscriptions_table").on("click", "#sub_audible_notifications_setting",
                                 stream_audible_notifications_clicked);
    $("#subscriptions_table").on("click", "#sub_push_notifications_setting",
                                 stream_push_notifications_clicked);
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
        // TODO: clean up this error handling
        var error_elem = settings_row.find('.subscriber_list_container .alert-error');
        var warning_elem = settings_row.find('.subscriber_list_container .alert-warning');

        function invite_success(data) {
            text_box.val('');

            if (data.subscribed.hasOwnProperty(principal)) {
                error_elem.addClass("hide");
                warning_elem.addClass("hide");
                if (people.is_current_user(principal)) {
                    // mark_subscribed adds the user to the member list
                    // TODO: We should really let the event system
                    //       handle this, as mark_subscribed has
                    //       lots of side effects.
                    stream_events.mark_subscribed(sub);
                }
            } else {
                error_elem.addClass("hide");
                warning_elem.removeClass("hide").text(i18n.t("User already subscribed"));
            }
        }

        function invite_failure() {
            warning_elem.addClass("hide");
            error_elem.removeClass("hide").text(i18n.t("Could not add user to this stream"));
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

        var error_elem = settings_row.find('.subscriber_list_container .alert-error');
        var warning_elem = settings_row.find('.subscriber_list_container .alert-warning');

        function removal_success(data) {
            if (data.removed.length > 0) {
                error_elem.addClass("hide");
                warning_elem.addClass("hide");

                // Remove the user from the subscriber list.
                list_entry.remove();

                if (people.is_current_user(principal)) {
                    // If you're unsubscribing yourself, mark whole
                    // stream entry as you being unsubscribed.
                    // TODO: We should really let the event system
                    //       handle this, as mark_unsubscribed has
                    //       lots of side effects.
                    stream_events.mark_unsubscribed(sub);
                }
            } else {
                error_elem.addClass("hide");
                warning_elem.removeClass("hide").text(i18n.t("User is already not subscribed"));
            }
        }

        function removal_failure() {
            warning_elem.addClass("hide");
            error_elem.removeClass("hide").text(i18n.t("Error removing user from this stream"));
        }

        exports.remove_user_from_stream(principal, sub, removal_success,
                                        removal_failure);
    });

    // This handler isn't part of the normal edit interface; it's the convenient
    // checkmark in the subscriber list.
    $("#subscriptions_table").on("click", ".sub_unsub_button", function (e) {
        var sub = get_sub_for_target(e.target);
        var stream_row = $(this).parent();
        var stream_id = stream_row.attr("data-stream-id");
        subs.sub_or_unsub(sub);
        var sub_settings = settings_for_sub(sub);
        var regular_sub_settings = sub_settings.find(".regular_subscription_settings");
        if (!sub.subscribed) {
            regular_sub_settings.addClass("in");
            exports.show_stream_row(stream_row, true);
        } else {
            regular_sub_settings.removeClass("in");
        }

        setup_subscriptions_stream_hash(sub, stream_id);
        e.preventDefault();
        e.stopPropagation();
    });

    $("#subscriptions_table").on("click", ".stream-row", function (e) {
        if ($(e.target).closest(".check, .subscription_settings").length === 0) {
            exports.show_stream_row(this, true);
            var stream_id = $(this).attr("data-stream-id");
            var sub = stream_data.get_sub_by_id(stream_id);
            setup_subscriptions_stream_hash(sub, stream_id);
        }
    });

    $(document).on('peer_subscribe.zulip', function (e, data) {
        var sub = stream_data.get_sub(data.stream_name);
        rerender_subscribers_list(sub);
    });

    $(document).on('peer_unsubscribe.zulip', function (e, data) {
        var sub = stream_data.get_sub(data.stream_name);
        rerender_subscribers_list(sub);
    });

});

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = stream_edit;
}
