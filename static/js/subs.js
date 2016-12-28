var subs = (function () {

var meta = {
    callbacks: {},
    stream_created: false
};
var exports = {};

function settings_for_sub(sub) {
    var id = parseInt(sub.stream_id, 10);
    return $("#subscription_overlay .subscription_settings[data-stream-id='" + id + "']");
}

function button_for_sub(sub) {
    var id = parseInt(sub.stream_id, 10);
    return $(".stream-row[data-stream-id='" + id + "'] .check");
}

function get_color() {
    var used_colors = stream_data.get_colors();
    var color = stream_color.pick_color(used_colors);
    return color;
}

function selectText(element) {
  var range;
  var sel;
    if (window.getSelection) {
        sel = window.getSelection();
        range = document.createRange();
        range.selectNodeContents(element);

        sel.removeAllRanges();
        sel.addRange(range);
    } else if (document.body.createTextRange) {
        range = document.body.createTextRange();
        range.moveToElementText(element);
        range.select();
    }
}

function should_list_all_streams() {
    return !page_params.is_zephyr_mirror_realm;
}

function set_stream_property(stream_name, property, value) {
    var sub_data = {stream: stream_name, property: property, value: value};
    return channel.post({
        url:      '/json/subscriptions/property',
        data: {subscription_data: JSON.stringify([sub_data])},
        timeout:  10*1000
    });
}

function set_notification_setting_for_all_streams(notification_type, new_setting) {
    _.each(stream_data.subscribed_subs(), function (sub) {
        if (sub[notification_type] !== new_setting) {
            set_stream_property(sub.name, notification_type, new_setting);
        }
    });
}

exports.set_all_stream_desktop_notifications_to = function (new_setting) {
    set_notification_setting_for_all_streams("desktop_notifications", new_setting);
};

exports.set_all_stream_audible_notifications_to = function (new_setting) {
    set_notification_setting_for_all_streams("audible_notifications", new_setting);
};


// Finds the stream name of a jquery object that's inside a
// .stream-row or .subscription_settings element.
function get_stream_name(target) {
    if (target.constructor !== jQuery) {
        target = $(target);
    }
    var stream_id = target.closest(".stream-row, .subscription_settings").attr("data-stream-id");
    return stream_data.get_sub_by_id(stream_id).name;
}

function stream_home_view_clicked(e) {
    var stream_name = get_stream_name(e.target);
    var sub = stream_data.get_sub(stream_name);
    var sub_settings = settings_for_sub(sub);
    var notification_checkboxes = sub_settings.find(".sub_notification_setting");

    subs.toggle_home(stream_name);

    if (sub.in_home_view) {
        sub_settings.find(".mute-note").addClass("hide-mute-note");
        notification_checkboxes.removeClass("muted-sub");
        notification_checkboxes.find("input[type='checkbox']").removeAttr("disabled");
    } else {
        sub_settings.find(".mute-note").removeClass("hide-mute-note");
        notification_checkboxes.addClass("muted-sub");
        notification_checkboxes.find("input[type='checkbox']").attr("disabled", true);
    }
}

function update_in_home_view(sub, value) {
    sub.in_home_view = value;

    setTimeout(function () {
        var msg_offset;
        var saved_ypos;
        // Save our current scroll position
        if (ui.home_tab_obscured()) {
            saved_ypos = viewport.scrollTop();
        } else if (home_msg_list === current_msg_list &&
                   current_msg_list.selected_row().offset() !== null) {
            msg_offset = current_msg_list.selected_row().offset().top;
        }

        home_msg_list.clear({clear_selected_id: false});

        // Recreate the home_msg_list with the newly filtered message_list.all
        message_store.add_messages(message_list.all.all_messages(), home_msg_list);

        // Ensure we're still at the same scroll position
        if (ui.home_tab_obscured()) {
            viewport.scrollTop(saved_ypos);
        } else if (home_msg_list === current_msg_list) {
            // We pass use_closest to handle the case where the
            // currently selected message is being hidden from the
            // home view
            home_msg_list.select_id(home_msg_list.selected_id(),
                                    {use_closest: true, empty_ok: true});
            if (current_msg_list.selected_id() !== -1) {
                viewport.set_message_offset(msg_offset);
            }
        }

        // In case we added messages to what's visible in the home view, we need to re-scroll to
        // make sure the pointer is still visible. We don't want the auto-scroll handler to move
        // our pointer to the old scroll location before we have a chance to update it.
        pointer.recenter_pointer_on_display = true;
        pointer.suppress_scroll_pointer_update = true;

        if (! home_msg_list.empty()) {
            message_store.do_unread_count_updates(home_msg_list.all_messages());
        }
    }, 0);

    stream_list.set_in_home_view(sub.name, sub.in_home_view);

    var not_in_home_view_checkbox = $(".subscription_settings[data-stream-id='" + sub.stream_id + "'] #sub_setting_not_in_home_view .sub_setting_control");
    not_in_home_view_checkbox.prop('checked', !value);
}

exports.toggle_home = function (stream_name) {
    var sub = stream_data.get_sub(stream_name);
    update_in_home_view(sub, ! sub.in_home_view);
    set_stream_property(stream_name, 'in_home_view', sub.in_home_view);
};

exports.toggle_pin_to_top_stream = function (stream_name) {
    var sub = stream_data.get_sub(stream_name);
    set_stream_property(stream_name, 'pin_to_top', !sub.pin_to_top);
};

function update_stream_desktop_notifications(sub, value) {
    var desktop_notifications_checkbox = $(".subscription_settings[data-stream-id='" + sub.stream_id + "'] #sub_desktop_notifications_setting .sub_setting_control");
    desktop_notifications_checkbox.prop('checked', value);
    sub.desktop_notifications = value;
}

function update_stream_audible_notifications(sub, value) {
    var audible_notifications_checkbox = $(".subscription_settings[data-stream-id='" + sub.stream_id + "'] #sub_audible_notifications_setting .sub_setting_control");
    audible_notifications_checkbox.prop('checked', value);
    sub.audible_notifications = value;
}

function update_stream_pin(sub, value) {
    var pin_checkbox = $('#pinstream-' + sub.stream_id);
    pin_checkbox.prop('checked', value);
    sub.pin_to_top = value;
}

function update_stream_name(stream_id, old_name, new_name) {
    // Rename the stream internally.
    var sub = stream_data.rename_sub(stream_id, new_name);

    // Update the left sidebar.
    stream_list.rename_stream(sub, new_name);

    // Update the stream settings
    var sub_settings = settings_for_sub(stream_data.get_sub_by_id(stream_id));
    sub_settings.find(".email-address").text(sub.email_address);
    sub_settings.find(".stream-name").text(new_name);

    // Update the subscriptions page
    var sub_row = $(".stream-row[data-stream-id='" + sub.stream_id + "']");
    sub_row.find(".stream-name").text(new_name);
    sub_row.attr("data-stream-name", new_name);

    // Update the message feed.
    _.each([home_msg_list, current_msg_list, message_list.all], function (list) {
        list.change_display_recipient(old_name, new_name);
    });
}

function update_stream_description(sub, description) {
    sub.description = description;

    // Update stream row
    var sub_row = $('.stream-row[data-stream-id=' + sub.stream_id + ']');
    sub_row.find(".description").text(description);

    // Update stream settings
    var settings = settings_for_sub(sub);
    settings.find('input.description').val(description);
    settings.find('.stream-description').text(description);
}

function stream_desktop_notifications_clicked(e) {
    var stream = get_stream_name(e.target);

    var sub = stream_data.get_sub(stream);
    sub.desktop_notifications = ! sub.desktop_notifications;
    set_stream_property(stream, 'desktop_notifications', sub.desktop_notifications);
}

function stream_audible_notifications_clicked(e) {
    var stream = get_stream_name(e.target);

    var sub = stream_data.get_sub(stream);
    sub.audible_notifications = ! sub.audible_notifications;
    set_stream_property(stream, 'audible_notifications', sub.audible_notifications);
}

function stream_pin_clicked(e) {
    var stream = get_stream_name(e.target);

    exports.toggle_pin_to_top_stream(stream);
}

exports.set_color = function (stream_id, color) {
    var sub = stream_data.get_sub_by_id(stream_id);
    set_stream_property(sub.name, 'color', color);
};

exports.rerender_subscribers_count = function (sub) {
    var id = parseInt(sub.stream_id, 10);
    stream_data.update_subscribers_count(sub);
    $(".stream-row[data-stream-id='" + id + "'] .subscriber-count-text").text(sub.subscriber_count);
};

function add_email_hint(row, email_address_hint_content) {
    // Add a popover explaining stream e-mail addresses on hover.
    var hint_id = "#email-address-hint-" + row.stream_id;
    var email_address_hint = $(hint_id);
    email_address_hint.popover({placement: "bottom",
                title: "Email integration",
                content: email_address_hint_content,
                trigger: "manual"});

    $("body").on("mouseover", hint_id, function (e) {
        email_address_hint.popover('show');
        e.stopPropagation();
    });
    $("body").on("mouseout", hint_id, function (e) {
        email_address_hint.popover('hide');
        e.stopPropagation();
    });
}

function add_sub_to_table(sub) {
    sub = stream_data.add_admin_options(sub);
    stream_data.update_subscribers_count(sub);
    var html = templates.render('subscription', sub);
    var settings_html = templates.render('subscription_settings', sub);
    $(".streams-list").append(html);
    $(".subscriptions .settings").append($(settings_html));

    var email_address_hint_content = templates.render('email_address_hint', { page_params: page_params });
    add_email_hint(sub, email_address_hint_content);

    if (meta.stream_created) {
        $(".stream-row[data-stream-name='" + meta.stream_created + "']").click();
        meta.stream_created = false;
    }
}

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

function prepend_subscriber(sub_row, email) {
    var list = get_subscriber_list(sub_row);
    list.prepend(format_member_list_elem(email));
}

function show_subscription_settings(sub_row) {
    var stream_id = sub_row.data("stream-id");
    var sub = stream_data.get_sub_by_id(stream_id);
    var sub_settings = settings_for_sub(sub);
    var warning_elem = sub_settings.find('.subscriber_list_container .alert-warning');
    var error_elem = sub_settings.find('.subscriber_list_container .alert-error');
    var indicator_elem = sub_settings.find('.subscriber_list_loading_indicator');

    if (!sub.render_subscribers) {
        return;
    }

    var list = get_subscriber_list(sub_settings);
    warning_elem.addClass('hide');
    error_elem.addClass('hide');
    list.empty();

    loading.make_indicator(indicator_elem);

    channel.get({
        url: "/json/streams/" + sub.name + "/members",
        idempotent: true,
        success: function (data) {
            loading.destroy_indicator(indicator_elem);
            var subscribers = _.map(data.subscribers, function (elem) {
                var person = people.get_by_email(elem);
                if (person === undefined) {
                    return elem;
                }
                return format_member_list_elem(elem);
            });
            _.each(subscribers.sort(), function (elem) {
                list.append(elem);
            });
        },
        error: function () {
            loading.destroy_indicator(indicator_elem);
            error_elem.removeClass("hide").text("Could not fetch subscriber list");
        }
    });

    sub_settings.find('input[name="principal"]').typeahead({
        source: people.get_realm_persons, // This is a function.
        items: 5,
        highlighter: function (item) {
            var item_formatted = typeahead_helper.render_person(item);
            return typeahead_helper.highlight_with_escaping(this.query, item_formatted);
        },
        matcher: function (item) {
            var query = $.trim(this.query.toLowerCase());
            if (query === '' || query === item.email) {
                return false;
            }
            // Case-insensitive.
            return (item.email.toLowerCase().indexOf(query) !== -1) ||
                (item.full_name.toLowerCase().indexOf(query) !== -1);
        },
        sorter: typeahead_helper.sort_recipientbox_typeahead,
        updater: function (item) {
            return item.email;
        }
    });

    var colorpicker = sub_settings.find('.colorpicker');
    var color = stream_data.get_color(sub.name);
    stream_color.set_colorpicker_color(colorpicker, color);
}

exports.show_settings_for = function (stream_name) {
    var sub_settings = settings_for_sub(stream_data.get_sub(stream_name));
    var stream = $(".subscription_settings[data-stream-name='" + stream_name + "']");
    $(".subscription_settings[data-stream].show").removeClass("show");

    $("#subscription_overlay .subscription_settings.show").removeClass("show");
    sub_settings.addClass("show");

    show_subscription_settings(stream);
};

exports.mark_subscribed = function (stream_name, attrs) {
    var sub = stream_data.get_sub(stream_name);

    if (sub === undefined) {
        blueslip.error('Unknown stream in mark_subscribed: ' + stream_name);
        return;
    }

    if (! sub.subscribed) {
        // Add yourself to a stream we already know about client-side.
        var color = get_color();
        exports.set_color(sub.stream_id, color);
        sub.subscribed = true;
        if (attrs) {
            stream_data.set_subscriber_emails(sub, attrs.subscribers);
        }
        var settings = settings_for_sub(sub);
        var button = button_for_sub(sub);

        if (button.length !== 0) {
            exports.rerender_subscribers_count(sub);

            button.toggleClass("checked");
            // Add the user to the member list if they're currently
            // viewing the members of this stream
            if (sub.render_subscribers && settings.hasClass('in')) {
                prepend_subscriber(settings,
                                   page_params.email);
            }
        } else {
            add_sub_to_table(sub);
        }

        // Display the swatch and subscription settings
        var sub_row = settings.closest('.stream-row');
        sub_row.find(".color_swatch").addClass('in');
        sub_row.find(".regular_subscription_settings").collapse('show');
    } else {
        // Already subscribed
        return;
    }

    if (current_msg_list.narrowed) {
        current_msg_list.update_trailing_bookend();
    }

    // Update unread counts as the new stream in sidebar might
    // need its unread counts re-calculated
    message_store.do_unread_count_updates(message_list.all.all_messages());

    $(document).trigger($.Event('subscription_add_done.zulip', {sub: sub}));
};

exports.mark_unsubscribed = function (stream_name) {
    var sub = stream_data.get_sub(stream_name);
    exports.mark_sub_unsubscribed(sub);
};

exports.mark_sub_unsubscribed = function (sub) {
    if (sub === undefined) {
        // We don't know about this stream
        return;
    } else if (sub.subscribed) {
        stream_data.unsubscribe_myself(sub);

        var button = button_for_sub(sub);
        button.toggleClass("checked");

        var settings = settings_for_sub(sub);
        if (settings.hasClass('in')) {
            settings.collapse('hide');
        }

        exports.rerender_subscribers_count(sub);

        // Hide the swatch and subscription settings
        var sub_row = settings.closest('.stream-row');
        sub_row.find(".color_swatch").removeClass('in');
        if (sub.render_subscribers) {
            // TODO: having a completely empty settings div messes
            // with Bootstrap's collapser.  We currently just ensure
            // that it's not empty for Zephyr mirror realms, even though it
            // looks weird
            sub_row.find(".regular_subscription_settings").collapse('hide');
        }
    } else {
        // Already unsubscribed
        return;
    }

    if (current_msg_list.narrowed) {
        current_msg_list.update_trailing_bookend();
    }

    $(document).trigger($.Event('subscription_remove_done.zulip', {sub: sub}));

    $(".stream-row[data-stream-id='" + sub.stream_id + "']").attr("data-temp-view", true);
};

// these streams are miscategorized so they don't jump off the page when being
// unsubscribed from, but should be cleared and sorted when you apply an actual
// filter.
function remove_temporarily_miscategorized_streams() {
    $("[data-temp-view]").removeAttr("data-temp-view", "false");
}

exports.remove_miscategorized_streams = remove_temporarily_miscategorized_streams;

function stream_matches_query(query, sub) {
    var search_terms = query.input.toLowerCase().split(",").map(function (s) {
        return s.trim();
    });

    var flag = true;
    flag = flag && (function () {
        var sub_name = sub.name.toLowerCase();

        return _.any(search_terms, function (o) {
            return new RegExp(o).test(sub_name);
        });
    }());
    flag = flag && ((sub.subscribed || !query.subscribed_only) ||
                    sub.data_temp_view === "true");
    return flag;
}

// query is now an object rather than a string.
// Query { input: String, subscribed_only: Boolean }
exports.filter_table = function (query) {
    _.each($("#subscriptions_table .stream-row"), function (row) {
        var sub = stream_data.get_sub_by_id($(row).attr("data-stream-id"));
        sub.data_temp_view = $(row).attr("data-temp-view");

        if (stream_matches_query(query, sub)) {
            $(row).removeClass("notdisplayed");
        } else {
            $(row).addClass("notdisplayed");
        }
    });

    if ($(".stream-row.active").hasClass("notdisplayed")) {
        $(".right .settings").hide();
        $(".nothing-selected").show();
        $(".stream-row.active").removeClass("active");
    }
};

function actually_filter_streams() {
    var search_box = $("#add_new_subscription input[type='text']");
    var query = search_box.expectOne().val().trim();
    var subscribed_only;
    if (components.toggle.lookup("stream-filter-toggle")) {
        subscribed_only = components.toggle.lookup("stream-filter-toggle").value() === "Subscribed";
    } else {
        subscribed_only = false;
    }
    exports.filter_table({ input: query, subscribed_only: subscribed_only });
}

var filter_streams = _.throttle(actually_filter_streams, 50);

exports.setup_page = function (callback) {
    function initialize_components() {
        var stream_filter_toggle = components.toggle({
            name: "stream-filter-toggle",
            selected: 0,
            values: [
                { label: "Subscribed" },
                { label: "All Streams" },
            ],
            callback: function () {
                actually_filter_streams();
                remove_temporarily_miscategorized_streams();
            }
        }).get();

        if (should_list_all_streams()) {
            $("#subscriptions_table .search-container").prepend(stream_filter_toggle);
        }

        // show the "Stream Settings" header by default.
        $(".display-type #stream_settings_title").show();
    }

    function _populate_and_fill() {
        var sub_rows = stream_data.get_streams_for_settings_page();

        $('#subscriptions_table').empty();

        var template_data = {
            can_create_streams: page_params.can_create_streams,
            subscriptions: sub_rows,
            hide_all_streams: !should_list_all_streams()
        };
        var rendered = templates.render('subscription_table_body', template_data);
        $('#subscriptions_table').append(rendered);
        initialize_components();
        actually_filter_streams();
        var email_address_hint_content = templates.render('email_address_hint', { page_params: page_params });
        _.each(sub_rows, function (row) {
            add_email_hint(row, email_address_hint_content);
        });

        $("#add_new_subscription input[type='text']").on("input", function () {
            remove_temporarily_miscategorized_streams();
            // Debounce filtering in case a user is typing quickly
            filter_streams();
        });

        $(document).trigger($.Event('subs_page_loaded.zulip'));

        if (callback) {
            callback();
            exports.onlaunchtrigger();
        }
    }

    function populate_and_fill() {
        i18n.ensure_i18n(function () {
            _populate_and_fill();
        });
    }

    populate_and_fill();

    if (!should_list_all_streams()) {
        $('#create_stream_button').val(i18n.t("Subscribe"));
    }
};

// add a function to run on subscription page launch by name,
// and specify whether it should be kept or just run once (boolean).
exports.onlaunch = function (name, callback, keep) {
    meta.callbacks[name] = {
        func: callback,
        keep: keep
    };
};

exports.onlaunchtrigger = function () {
    for (var x in meta.callbacks) {
        if (typeof meta.callbacks[x].func === "function") {
            meta.callbacks[x].func();

            // delete if it should not be kept.
            if (!meta.callbacks[x].keep) {
                delete meta.callbacks[x];
            }
        }
    }
};

exports.launch = function () {
    exports.setup_page(function () {
        $("#subscription_overlay").fadeIn(300);
    });
};

exports.update_subscription_properties = function (stream_name, property, value) {
    var sub = stream_data.get_sub(stream_name);
    if (sub === undefined) {
        // This isn't a stream we know about, so ignore it.
        blueslip.warn("Update for an unknown subscription", {stream_name: stream_name,
                                                            property: property,
                                                            value: value});
        return;
    }
    switch (property) {
    case 'color':
        stream_color.update_stream_color(sub, stream_name, value, {update_historical: true});
        break;
    case 'in_home_view':
        update_in_home_view(sub, value);
        break;
    case 'desktop_notifications':
        update_stream_desktop_notifications(sub, value);
        break;
    case 'audible_notifications':
        update_stream_audible_notifications(sub, value);
        break;
    case 'name':
        update_stream_name(sub.stream_id, sub.name, value);
        break;
    case 'description':
        update_stream_description(sub, value);
        break;
    case 'email_address':
        sub.email_address = value;
        break;
    case 'pin_to_top':
        update_stream_pin(sub, value);
        stream_list.refresh_pinned_or_unpinned_stream(sub);
        break;
    default:
        blueslip.warn("Unexpected subscription property type", {property: property,
                                                                value: value});
    }
};

function ajaxSubscribe(stream) {
    // Subscribe yourself to a single stream.
    var true_stream_name;

    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([{name: stream}]) },
        success: function (resp, statusText, xhr) {
            $("#create_stream_name").val("");

            actually_filter_streams();

            var res = JSON.parse(xhr.responseText);
            if (!$.isEmptyObject(res.already_subscribed)) {
                // Display the canonical stream capitalization.
                true_stream_name = res.already_subscribed[page_params.email][0];
                ui.report_success(i18n.t("Already subscribed to __stream__", {stream: true_stream_name}),
                                  $("#subscriptions-status"), 'subscriptions-status');
            }
            // The rest of the work is done via the subscribe event we will get
        },
        error: function (xhr) {
            ui.report_error(i18n.t("Error adding subscription"), xhr,
                            $("#subscriptions-status"), 'subscriptions-status');
        }
    });
}

function ajaxUnsubscribe(stream) {
    return channel.del({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([stream]) },
        success: function () {
            $("#subscriptions-status").hide();
            // The rest of the work is done via the unsubscribe event we will get
        },
        error: function (xhr) {
            ui.report_error(i18n.t("Error removing subscription"), xhr,
                            $("#subscriptions-status"), 'subscriptions-status');
        }
    });
}

function ajaxSubscribeForCreation(stream, description, principals, invite_only, announce) {
    // Subscribe yourself and possible other people to a new stream.
    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([{name: stream, description: description}]),
               principals: JSON.stringify(principals),
               invite_only: JSON.stringify(invite_only),
               announce: JSON.stringify(announce)
        },
        success: function () {
            $("#create_stream_name").val("");
            $("#create_stream_description").val("");
            $("#subscriptions-status").hide();
            // The rest of the work is done via the subscribe event we will get
        },
        error: function (xhr) {
            ui.report_error(i18n.t("Error creating stream"), xhr,
                            $("#subscriptions-status"), 'subscriptions-status');
        }
    });
}

// Within the new stream modal...
function update_announce_stream_state() {
    // If the stream is invite only, or everyone's added, disable
    // the "Announce stream" option. Otherwise enable it.
    var announce_stream_checkbox = $('#announce-new-stream input');
    var disable_it = false;
    var is_invite_only = $('input:radio[name=privacy]:checked').val() === 'invite-only';

    if (is_invite_only) {
        disable_it = true;
        announce_stream_checkbox.prop('checked', false);
    } else {
        disable_it = $('#user-checkboxes input').length
                    === $('#user-checkboxes input:checked').length;
    }

    announce_stream_checkbox.prop('disabled', disable_it);
}

function show_new_stream_modal() {
    $("#stream-creation").removeClass("hide");
    $(".right .settings").hide();
    $('#people_to_add').html(templates.render('new_stream_users', {
        users: people.get_rest_of_realm(),
        streams: stream_data.get_streams_for_settings_page()
    }));

    // Make the options default to the same each time:
    // public, "announce stream" on.
    $('#make-invite-only input:radio[value=public]').prop('checked', true);
    $('#announce-new-stream input').prop('disabled', false);
    $('#announce-new-stream input').prop('checked', true);

    $("#stream_name_error").hide();
}

exports.invite_user_to_stream = function (user_email, stream_name, success, failure) {
    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([{name: stream_name}]),
               principals: JSON.stringify([user_email])},
        success: success,
        error: failure
    });
};

exports.remove_user_from_stream = function (user_email, stream_name, success, failure) {
    return channel.del({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([stream_name]),
               principals: JSON.stringify([user_email])},
        success: success,
        error: failure
    });
};

$(function () {

    stream_data.initialize_from_page_params();
    stream_list.create_initial_sidebar_rows();

    // We build the stream_list now.  It may get re-built again very shortly
    // when new messages come in, but it's fairly quick.
    stream_list.build_stream_list();

    var show_subs_pane = {
        nothing_selected: function () {
            $(".nothing-selected, #stream_settings_title").show();
            $("#add_new_stream_title, .settings, #stream-creation").hide();
        },
        stream_creation: function () {
            $("#stream-creation, #add_new_stream_title").show();
            $("#stream_settings_title, .settings, .nothing-selected").hide();
        },
        settings: function () {
            $(".settings, #stream_settings_title").show();
            $("#add_new_stream_title, #stream-creation, .nothing-selected").hide();
        },
    };

    $("#subscriptions_table").on("click", "#create_stream_button", function (e) {
        e.preventDefault();
        // this changes the tab switcher (settings/preview) which isn't necessary
        // to a add new stream title.
        $(".display-type #add_new_stream_title").show();
        $(".display-type #stream_settings_title").hide();

        $(".stream-row.active").removeClass("active");

        show_subs_pane.stream_creation();

        if (!should_list_all_streams()) {
            ajaxSubscribe($("#search_stream_name").val());
            return;
        }

        var stream = $.trim($("#search_stream_name").val());
        $('#create_stream_name').val(stream);
        show_new_stream_modal();
        $('#create_stream_name').focus();
    });

    $('body').on('change', '#user-checkboxes input, #make-invite-only input', update_announce_stream_state);


    $(".subscriptions").on("click", "[data-dismiss]", function (e) {
        e.preventDefault();
        // we want to make sure that the click is not just a simulated
        // click; this fixes an issue where hitting "enter" would
        // trigger this code path due to bootstrap magic.
        if (e.clientY !== 0) {
            show_subs_pane.nothing_selected();
        }
    });

    // 'Check all' and 'Uncheck all' links
    $(document).on('click', '.subs_set_all_users', function (e) {
        $('#people_to_add :checkbox').prop('checked', true);
        e.preventDefault();
        update_announce_stream_state();
    });
    $(document).on('click', '.subs_unset_all_users', function (e) {
        $('#people_to_add :checkbox').prop('checked', false);
        e.preventDefault();
        update_announce_stream_state();
    });
    $(document).on('click', '#copy-from-stream-expand-collapse', function (e) {
        $('#stream-checkboxes').toggle();
        $("#copy-from-stream-expand-collapse .toggle").toggleClass('icon-vector-caret-right icon-vector-caret-down');
        e.preventDefault();
        update_announce_stream_state();
    });

    // Search People or Streams
    $(document).on('input', '.add-user-list-filter', function (e) {
        var users = people.get_rest_of_realm();
        var streams = stream_data.get_streams_for_settings_page();

        var user_list = $(".add-user-list-filter");
        if (user_list === 0) {
            return;
        }
        var search_term = user_list.expectOne().val().trim();
        var search_terms = search_term.toLowerCase().split(",");
        var filtered_users = people.filter_people_by_search_terms(users, search_terms);

        _.each(streams, function (stream) {
            var flag = true;

            flag = flag && (function () {
                var sub_name = stream.name.toLowerCase();
                var matches_list = search_terms.indexOf(sub_name) > -1;
                var matches_last_val = sub_name.match(search_terms[search_terms.length - 1]);
                return matches_list || matches_last_val;
            }());

            if (flag) {
                $("label[data-name='" + stream.name + "']").css("display", "block");
            } else {
                $("label[data-name='" + stream.name + "']").css("display", "none");
            }
        });

        // Hide users which aren't in filtered users
        _.each(users, function (user) {
            var display_type = filtered_users.hasOwnProperty(user.email)? "block" : "none";
            $("label[data-name='" + user.email + "']").css({display: display_type});
        });

        update_announce_stream_state();
        e.preventDefault();
    });

    $("body").on("mouseover", "#announce-stream-docs", function (e) {
        var announce_stream_docs = $("#announce-stream-docs");
        announce_stream_docs.popover({placement: "right",
                                      content: templates.render('announce_stream_docs'),
                                      trigger: "manual"});
        announce_stream_docs.popover('show');
        announce_stream_docs.data('popover').tip().css('z-index', 2000);
        e.stopPropagation();
    });
    $("body").on("mouseout", "#announce-stream-docs", function (e) {
        $("#announce-stream-docs").popover('hide');
        e.stopPropagation();
    });

    $(".subscriptions").on("focusout", "#create_stream_name", function () {
        var stream = $.trim($("#create_stream_name").val());
        if (stream.length !== 0) {
            var stream_status = compose.check_stream_existence(stream);

            if (stream_status !== "does-not-exist") {
                $("#stream_name_error").text(i18n.t("A stream with this name already exists"));
                $("#stream_name_error").show();
            } else {
                $("#stream_name_error").hide();
            }
        } else {
            $("#stream_name_error").text(i18n.t("A stream needs to have a name"));
            $("#stream_name_error").show();
        }
    });

    $(".subscriptions").on("submit", "#stream_creation_form", function (e) {
        e.preventDefault();
        var stream = $.trim($("#create_stream_name").val());
        var description = $.trim($("#create_stream_description").val());
        if (!$("#stream_name_error").is(":visible")) {
            var principals = _.map(
                $("#stream_creation_form input:checkbox[name=user]:checked"),
                function (elem) {
                    return $(elem).val();
                }
            );

            var checked_streams = _.map(
                $("#stream_creation_form input:checkbox[name=stream]:checked"),
                function (elem) {
                    return $(elem).val();
                }
            );

            var checked_stream_emails = [];
            var stream_emails = [];

            _.each(checked_streams, function (checked_stream) {
                stream_emails = [];
                var subscriber_ids = stream_data.get_sub(checked_stream).subscribers.keys();
                _.each(subscriber_ids, function (subscriber_id) {
                    stream_emails.push(people.get_person_from_user_id(subscriber_id).email);
                });
                checked_stream_emails = _.union(checked_stream_emails, stream_emails);
            });

            // If a stream was checked and the checkboxes are not visible,
            // don't add checked streams
            if ($('#stream-checkboxes').css('display') !== 'none') {
                principals = _.union(principals, checked_stream_emails);
            }


            // You are always subscribed to streams you create.
            principals.push(page_params.email);

            meta.stream_created = stream;

            ajaxSubscribeForCreation(stream,
                description,
                principals,
                $('#stream_creation_form input[name=privacy]:checked').val() === "invite-only",
                $('#announce-new-stream input').prop('checked')
            );
        }
    });

    $("body").on("mouseover", ".subscribed-button", function (e) {
        $(e.target).addClass("btn-danger").text(i18n.t("Unsubscribe"));
    }).on("mouseout", ".subscribed-button", function (e) {
        $(e.target).removeClass("btn-danger").text(i18n.t("Subscribed"));
    });

    $(".subscriptions").on("click", "#close-subscriptions-status", function () {
        $("#subscriptions-status").hide();
    });

    $("#subscriptions_table").on("click", ".email-address", function () {
        selectText(this);
    });

    function sub_or_unsub(stream_name) {
        var sub = stream_data.get_sub(stream_name);

        if (sub.subscribed) {
            ajaxUnsubscribe(stream_name);
        } else {
            ajaxSubscribe(stream_name);
        }
    }

    $("#subscriptions_table").on("click", ".sub_unsub_button", function (e) {
        var stream_name = get_stream_name(e.target);
        sub_or_unsub(stream_name);
        e.preventDefault();
        e.stopPropagation();
    });

    $("body").on("click", ".popover_sub_unsub_button", function (e) {
        $(this).toggleClass("unsub");
        $(this).closest(".popover").fadeOut(500).delay(500).remove();

        var stream_name = $(e.target).data("name");

        sub_or_unsub(stream_name);
        e.preventDefault();
        e.stopPropagation();
    });

    $("#zfilt").on("click", ".stream_sub_unsub_button", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var stream_name = narrow.stream();
        if (stream_name === undefined) {
            return;
        }
        var sub = stream_data.get_sub(stream_name);

        if (sub.subscribed) {
            ajaxUnsubscribe(stream_name);
        } else {
            ajaxSubscribe(stream_name);
        }
    });

    $('.empty_feed_sub_unsub').click(function (e) {
        e.preventDefault();

        $('#subscription-status').hide();
        var stream_name = narrow.stream();
        if (stream_name === undefined) {
            return;
        }
        var sub = stream_data.get_sub(stream_name);

        if (sub.subscribed) {
            ajaxUnsubscribe(stream_name);
        } else {
            ajaxSubscribe(stream_name);
        }
        $('.empty_feed_notice').hide();
        $('#empty_narrow_message').show();
    });

    $("#subscriptions_table").on("click", ".sub_setting_checkbox", function (e) {
        var control = $(e.target).closest('.sub_setting_checkbox').find('.sub_setting_control');
        // A hack.  Don't change the state of the checkbox if we
        // clicked on the checkbox itself.
        if (control[0] !== e.target) {
            control.prop("checked", ! control.prop("checked"));
        }
    });
    $("#subscriptions_table").on("click", "#sub_setting_not_in_home_view", stream_home_view_clicked);
    $("#subscriptions_table").on("click", "#sub_desktop_notifications_setting",
                                 stream_desktop_notifications_clicked);
    $("#subscriptions_table").on("click", "#sub_audible_notifications_setting",
                                 stream_audible_notifications_clicked);
    $("#subscriptions_table").on("click", "#sub_pin_setting",
                                 stream_pin_clicked);

    $("#subscriptions_table").on("submit", ".subscriber_list_add form", function (e) {
        e.preventDefault();
        var settings_row = $(e.target).closest('.subscription_settings');
        var stream = get_stream_name(settings_row);
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
                if (util.is_current_user(principal)) {
                    // mark_subscribed adds the user to the member list
                    exports.mark_subscribed(stream);
                }
            } else {
                error_elem.addClass("hide");
                warning_elem.removeClass("hide").text("User already subscribed");
            }
        }

        function invite_failure() {
            warning_elem.addClass("hide");
            error_elem.removeClass("hide").text("Could not add user to this stream");
        }

        exports.invite_user_to_stream(principal, stream, invite_success, invite_failure);
    });

    function show_stream_row(node, e) {
        $(".display-type #add_new_stream_title").hide();
        $(".display-type #stream_settings_title, .right .settings").show();
        $(".stream-row.active").removeClass("active");
        if (e) {
            show_subs_pane.settings();

            $(node).addClass("active");
            exports.show_settings_for(get_stream_name(node));
        } else {
            show_subs_pane.nothing_selected();
        }
    }

    $("#subscriptions_table").on("click", ".stream-row", function (e) {
        if ($(e.target).closest(".check, .subscription_settings").length === 0) {
            show_stream_row(this, e);
        }
    });

    (function defocus_sub_settings() {
        var sel = ".search-container, .streams-list, .subscriptions-header";

        $("#subscriptions_table").on("click", sel, function (e) {
            if ($(e.target).is(sel)) {
                show_stream_row(this);
            }
        });
    }());

    $("#subscriptions_table").on("submit", ".subscriber_list_remove form", function (e) {
        e.preventDefault();

        var list_entry = $(e.target).closest("tr");
        var principal = list_entry.children(".subscriber-email").text();
        var settings_row = $(e.target).closest('.subscription_settings');
        var stream_name = get_stream_name(settings_row);
        var error_elem = settings_row.find('.subscriber_list_container .alert-error');
        var warning_elem = settings_row.find('.subscriber_list_container .alert-warning');

        function removal_success(data) {
            if (data.removed.length > 0) {
                error_elem.addClass("hide");
                warning_elem.addClass("hide");

                // Remove the user from the subscriber list.
                list_entry.remove();

                if (util.is_current_user(principal)) {
                    // If you're unsubscribing yourself, mark whole
                    // stream entry as you being unsubscribed.
                    exports.mark_unsubscribed(stream_name);
                }
            } else {
                error_elem.addClass("hide");
                warning_elem.removeClass("hide").text("User already not subscribed");
            }
        }

        function removal_failure() {
            warning_elem.addClass("hide");
            error_elem.removeClass("hide").text("Could not remove user from this stream");
        }

        exports.remove_user_from_stream(principal, stream_name, removal_success,
                                        removal_failure);
    });

    $("#subscriptions_table").on("submit", ".rename-stream form", function (e) {
        e.preventDefault();
        var sub_settings = $(e.target).closest('.subscription_settings');
        var stream_id = $(e.target).closest(".subscription_settings").attr("data-stream-id");
        var sub = stream_data.get_sub_by_id(stream_id);
        var new_name_box = sub_settings.find('input[name="new-name"]');
        var new_name = $.trim(new_name_box.val());

        $("#subscriptions-status").hide();

        channel.patch({
            // Stream names might contain unsafe characters so we must encode it first.
            url: "/json/streams/" + encodeURIComponent(sub.name),
            data: {new_name: JSON.stringify(new_name)},
            success: function () {
                new_name_box.val('');
                ui.report_success(i18n.t("The stream has been renamed!"), $("#subscriptions-status "),
                                  'subscriptions-status');
            },
            error: function (xhr) {
                ui.report_error(i18n.t("Error renaming stream"), xhr,
                                $("#subscriptions-status"), 'subscriptions-status');
            }
        });
    });

    $('#subscriptions_table').on('submit', '.change-stream-description form', function (e) {
        e.preventDefault();
        var sub_settings = $(e.target).closest('.subscription_settings');
        var stream_name = get_stream_name(sub_settings);
        var description = sub_settings.find('input[name="description"]').val();

        $('#subscriptions-status').hide();

        channel.patch({
            // Stream names might contain unsafe characters so we must encode it first.
            url: '/json/streams/' + encodeURIComponent(stream_name),
            data: {
                description: JSON.stringify(description)
            },
            success: function () {
                // The event from the server will update the rest of the UI
                ui.report_success(i18n.t("The stream description has been updated!"),
                                 $("#subscriptions-status"), 'subscriptions-status');
            },
            error: function (xhr) {
                ui.report_error(i18n.t("Error updating the stream description"), xhr,
                                $("#subscriptions-status"), 'subscriptions-status');
            }
        });
    });

    function redraw_privacy_related_stuff(sub_row, sub) {
        var stream_settings = settings_for_sub(sub);
        var html;

        sub = stream_data.add_admin_options(sub);

        html = templates.render('subscription_setting_icon', sub);
        sub_row.find('.icon').expectOne().replaceWith($(html));

        html = templates.render('subscription_type', sub);
        stream_settings.find('.subscription-type').expectOne().html(html);

        if (sub.invite_only) {
            stream_settings.find(".large-icon")
                .removeClass("hash").addClass("lock")
                .html("<i class='icon-vector-lock'></i>");
        } else {
            stream_settings.find(".large-icon")
                .addClass("hash").removeClass("lock")
                .html("");
        }

        html = templates.render('change_stream_privacy', sub);
        stream_settings.find('.change-stream-privacy').expectOne().html(html);

        stream_list.redraw_stream_privacy(sub.name);
    }

    function change_stream_privacy(e, is_private, success_message, error_message, invite_only) {
        e.preventDefault();

        var stream_id = $(e.target).closest(".subscription_settings").attr("data-stream-id");
        var sub = stream_data.get_sub_by_id(stream_id);

        $("#subscriptions-status").hide();
        var data = {stream_name: sub.name, is_private: is_private};

        channel.patch({
            url: "/json/streams/" + sub.name,
            data: data,
            success: function () {
                sub = stream_data.get_sub_by_id(stream_id);
                var stream_settings = settings_for_sub(sub);
                var sub_row = $(".stream-row[data-stream-id='" + stream_id + "']");
                sub.invite_only = invite_only;
                redraw_privacy_related_stuff(sub_row, sub);
                var feedback_div = stream_settings.find(".change-stream-privacy-feedback").expectOne();
                ui.report_success(success_message, feedback_div);
            },
            error: function (xhr) {
                var stream_settings = settings_for_sub(sub);
                var feedback_div = stream_settings.find(".change-stream-privacy-feedback").expectOne();
                ui.report_error(error_message, xhr, feedback_div);
            }
        });
    }

    $("#subscriptions_table").on("click", ".make-stream-public-button", function (e) {
        change_stream_privacy(
            e,
            false,
            "The stream has been made public!",
            "Error making stream public",
            false
        );
    });

    $("#subscriptions_table").on("click", ".make-stream-private-button", function (e) {
        change_stream_privacy(
            e,
            true,
            "The stream has been made private!",
            "Error making stream private",
            true
        );
    });

    $("#subscriptions_table").on("show", ".regular_subscription_settings", function (e) {
        // We want 'show' events that originate from
        // 'regular_subscription_settings' divs not to trigger the
        // handler for the entire subscription_settings div
        e.stopPropagation();
    });

    $("#subscriptions_table").on("hide", ".subscription_settings", function (e) {
        var sub_arrow = $(e.target).closest('.stream-row').find('.sub_arrow i');
        sub_arrow.removeClass('icon-vector-chevron-up');
        sub_arrow.addClass('icon-vector-chevron-down');
    });

    $(document).on('peer_subscribe.zulip', function (e, data) {
        var sub = stream_data.get_sub(data.stream_name);
        exports.rerender_subscribers_count(sub);
        var sub_row = settings_for_sub(sub);
        prepend_subscriber(sub_row, data.user_email);
    });
    $(document).on('peer_unsubscribe.zulip', function (e, data) {
        var sub = stream_data.get_sub(data.stream_name);
        exports.rerender_subscribers_count(sub);

        var sub_row = settings_for_sub(sub);
        var tr = sub_row.find("tr[data-subscriber-email='" +
                              data.user_email +
                              "']");
        tr.remove();
    });

});

function focus_on_narrowed_stream() {
    var stream_name = narrow.stream();
    if (stream_name === undefined) {
        return;
    }
    var sub = stream_data.get_sub(stream_name);
    if (sub === undefined) {
        // This stream doesn't exist, so prep for creating it.
        $("#create_stream_name").val(stream_name);
    }
}

exports.show_and_focus_on_narrow = function () {
    $(document).one('subs_page_loaded.zulip', focus_on_narrowed_stream);
    ui.change_tab_to("#subscriptions");
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = subs;
}
