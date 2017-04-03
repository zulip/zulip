var subs = (function () {

var meta = {
    callbacks: {},
    stream_created: undefined,
    is_open: false,
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

function row_for_stream_id(stream_id) {
    return $(".stream-row[data-stream-id='" + stream_id + "']");
}

function settings_button_for_sub(sub) {
    var id = parseInt(sub.stream_id, 10);
    return $(".subscription_settings[data-stream-id='" + id + "'] .subscribe-button");
}

function get_row_data(row) {
    var row_id = row.attr('data-stream-id');
    if (row_id) {
        var row_object = stream_data.get_sub_by_id(row_id);
        return {
            id: row_id,
            object: row_object,
        };
    }
}

function get_active_data() {
    var active_row = $('div.stream-row.active');
    var valid_active_id = active_row.attr('data-stream-id');
    var active_tab = $('.subscriptions-container').find('div.ind-tab.selected');
    return {
        row: active_row,
        id: valid_active_id,
        tab: active_tab,
    };
}

function export_hash(hash) {
    var hash_components = {
        base: hash.shift(),
        arguments: hash,
    };
    exports.change_state(hash_components);
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

function set_stream_property(sub, property, value) {
    // TODO: Fix backend so it takes a stream id.
    var stream_name = sub.name;
    var sub_data = {stream: stream_name, property: property, value: value};
    return channel.post({
        url:      '/json/subscriptions/property',
        data: {subscription_data: JSON.stringify([sub_data])},
        timeout:  10*1000,
    });
}

function set_notification_setting_for_all_streams(notification_type, new_setting) {
    _.each(stream_data.subscribed_subs(), function (sub) {
        if (sub[notification_type] !== new_setting) {
            set_stream_property(sub, notification_type, new_setting);
        }
    });
}

exports.set_all_stream_desktop_notifications_to = function (new_setting) {
    set_notification_setting_for_all_streams("desktop_notifications", new_setting);
};

exports.set_all_stream_audible_notifications_to = function (new_setting) {
    set_notification_setting_for_all_streams("audible_notifications", new_setting);
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
        notification_checkboxes.find("input[type='checkbox']").removeAttr("disabled");
    } else {
        sub_settings.find(".mute-note").removeClass("hide-mute-note");
        notification_checkboxes.addClass("muted-sub");
        notification_checkboxes.find("input[type='checkbox']").attr("disabled", true);
    }
}

exports.toggle_home = function (sub) {
    stream_muting.update_in_home_view(sub, ! sub.in_home_view);
    set_stream_property(sub, 'in_home_view', sub.in_home_view);
};

exports.toggle_pin_to_top_stream = function (sub) {
    set_stream_property(sub, 'pin_to_top', !sub.pin_to_top);
};

exports.update_stream_name = function (sub, new_name) {
    // Rename the stream internally.
    stream_data.rename_sub(sub, new_name);
    var stream_id = sub.stream_id;

    // Update the left sidebar.
    stream_list.rename_stream(sub, new_name);

    // Update the stream settings
    var sub_settings = settings_for_sub(stream_data.get_sub_by_id(stream_id));
    sub_settings.find(".email-address").text(sub.email_address);
    sub_settings.find(".stream-name-editable").text(new_name);

    // Update the subscriptions page
    var sub_row = $(".stream-row[data-stream-id='" + stream_id + "']");
    sub_row.find(".stream-name").text(new_name);

    // Update the message feed.
    message_live_update.update_stream_name(stream_id, new_name);
};

exports.update_stream_description = function (sub, description) {
    sub.description = description;

    // Update stream row
    var sub_row = $('.stream-row[data-stream-id=' + sub.stream_id + ']');
    stream_data.render_stream_description(sub);
    sub_row.find(".description").html(sub.rendered_description);

    // Update stream settings
    var stream_settings = settings_for_sub(sub);
    stream_settings.find('input.description').val(sub.description);
    stream_settings.find('.stream-description-editable').html(sub.rendered_description);
};

function stream_desktop_notifications_clicked(e) {
    var sub = get_sub_for_target(e.target);
    sub.desktop_notifications = ! sub.desktop_notifications;
    set_stream_property(sub, 'desktop_notifications', sub.desktop_notifications);
}

function stream_audible_notifications_clicked(e) {
    var sub = get_sub_for_target(e.target);
    sub.audible_notifications = ! sub.audible_notifications;
    set_stream_property(sub, 'audible_notifications', sub.audible_notifications);
}

function stream_pin_clicked(e) {
    var sub = get_sub_for_target(e.target);
    if (!sub) {
        blueslip.error('stream_pin_clicked() fails');
        return;
    }
    exports.toggle_pin_to_top_stream(sub);
}

exports.set_color = function (stream_id, color) {
    var sub = stream_data.get_sub_by_id(stream_id);
    set_stream_property(sub, 'color', color);
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

// The `meta.stream_created` flag tells us whether the stream was just
// created in this browser window; it's a hack to work around the
// server_events code flow not having a good way to associate with
// this request.  These should be appended to the top of the list so
// they are more visible.
function add_sub_to_table(sub) {
    sub = stream_data.add_admin_options(sub);
    stream_data.update_subscribers_count(sub);
    stream_data.render_stream_description(sub);
    var html = templates.render('subscription', sub);
    var settings_html = templates.render('subscription_settings', sub);
    if (meta.stream_created === sub.name) {
        $(".streams-list").prepend(html).scrollTop(0);
    } else {
        $(".streams-list").append(html);
    }
    $(".subscriptions .settings").append($(settings_html));

    var email_address_hint_content = templates.render('email_address_hint', { page_params: page_params });
    add_email_hint(sub, email_address_hint_content);

    if (meta.stream_created === sub.name) {
        $(".stream-row[data-stream-id='" + stream_data.get_sub(meta.stream_created).stream_id + "']").click();
        meta.stream_created = undefined;
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

exports.remove_stream = function (stream_id) {
    // It is possible that row is empty when we deactivate a
    // stream, but we let jQuery silently handle that.
    var row = row_for_stream_id(stream_id);
    row.remove();
};

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
        url: "/json/streams/" + stream_id + "/members",
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

            var list_html = _.reduce(subscribers.sort(), function (accumulator, item) {
                return accumulator + item;
            }, "");

            list.append(list_html);
        },
        error: function () {
            loading.destroy_indicator(indicator_elem);
            error_elem.removeClass("hide").text(i18n.t("Could not fetch subscriber list"));
        },
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
        sorter: function (matches) {
            var current_stream = compose.stream_name();
            return typeahead_helper.sort_recipientbox_typeahead(
                this.query, matches, current_stream);
        },
        updater: function (item) {
            return item.email;
        },
    });

    var colorpicker = sub_settings.find('.colorpicker');
    var color = stream_data.get_color(sub.name);
    stream_color.set_colorpicker_color(colorpicker, color);
}

exports.show_settings_for = function (stream_id) {
    var sub = stream_data.get_sub_by_id(stream_id);
    var sub_settings = settings_for_sub(sub);

    var sub_row = $(".subscription_settings[data-stream-id='" + stream_id + "']");
    $(".subscription_settings[data-stream].show").removeClass("show");

    $("#subscription_overlay .subscription_settings.show").removeClass("show");
    sub_settings.addClass("show");

    show_subscription_settings(sub_row);
};

exports.update_settings_for_subscribed = function (sub) {
    var stream_settings = settings_for_sub(sub);
    var button = button_for_sub(sub);
    var settings_button = settings_button_for_sub(sub).removeClass("unsubscribed");

    if (button.length !== 0) {
        exports.rerender_subscribers_count(sub);

        button.toggleClass("checked");
        settings_button.text(i18n.t("Unsubscribe"));
        // Add the user to the member list if they're currently
        // viewing the members of this stream
        if (sub.render_subscribers && stream_settings.hasClass('in')) {
            prepend_subscriber(stream_settings,
                               people.my_current_email());
        }
    } else {
        add_sub_to_table(sub);
    }

    // Display the swatch and subscription stream_settings
    var sub_row = stream_settings.closest('.stream-row');
    sub_row.find(".regular_subscription_settings").addClass('in');
};

exports.update_settings_for_unsubscribed = function (sub) {
    var button = button_for_sub(sub);
    var settings_button = settings_button_for_sub(sub).addClass("unsubscribed");

    button.toggleClass("checked");
    settings_button.text(i18n.t("Subscribe"));

    var stream_settings = settings_for_sub(sub);
    if (stream_settings.hasClass('in')) {
        stream_settings.collapse('hide');
    }

    exports.rerender_subscribers_count(sub);

    // Hide the swatch and subscription settings
    var sub_row = stream_settings.closest('.stream-row');
    sub_row.find(".regular_subscription_settings").removeClass('in');
    row_for_stream_id(subs.stream_id).attr("data-temp-view", true);
};

// these streams are miscategorized so they don't jump off the page when being
// unsubscribed from, but should be cleared and sorted when you apply an actual
// filter.
function remove_temporarily_miscategorized_streams() {
    $("[data-temp-view]").removeAttr("data-temp-view", "false");
}

exports.remove_miscategorized_streams = remove_temporarily_miscategorized_streams;

function stream_matches_query(query, sub, attr) {
    var search_terms = query.input.toLowerCase().split(",").map(function (s) {
        return s.trim();
    });

    var flag = true;
    flag = flag && (function () {
        var sub_attr = sub[attr].toLowerCase();
        return _.any(search_terms, function (o) {
            if (sub_attr.indexOf(o) !== -1) {
                return true;
            }
        });
    }());
    flag = flag && ((sub.subscribed || !query.subscribed_only) ||
                    sub.data_temp_view === "true");
    return flag;
}
exports.stream_name_match_stream_ids = [];
exports.stream_description_match_stream_ids = [];

// query is now an object rather than a string.
// Query { input: String, subscribed_only: Boolean }
exports.filter_table = function (query) {
    exports.stream_name_match_stream_ids = [];
    exports.stream_description_match_stream_ids = [];
    var others = [];
    var stream_id_to_stream_name = {};
    var widgets = {};

    function sort_by_stream_name(a, b) {
        var stream_a_name = stream_id_to_stream_name[a].toLocaleLowerCase();
        var stream_b_name = stream_id_to_stream_name[b].toLocaleLowerCase();
        return String.prototype.localeCompare.call(stream_a_name, stream_b_name);
    }

    _.each($("#subscriptions_table .stream-row"), function (row) {
        var sub = stream_data.get_sub_by_id($(row).attr("data-stream-id"));
        sub.data_temp_view = $(row).attr("data-temp-view");

        if (stream_matches_query(query, sub, 'name')) {
            $(row).removeClass("notdisplayed");

            stream_id_to_stream_name[sub.stream_id] = sub.name;
            exports.stream_name_match_stream_ids.push(sub.stream_id);

            widgets[sub.stream_id] = $(row).detach();
        } else if (stream_matches_query(query, sub, 'description')) {
            $(row).removeClass("notdisplayed");

            stream_id_to_stream_name[sub.stream_id] = sub.name;
            exports.stream_description_match_stream_ids.push(sub.stream_id);

            widgets[sub.stream_id] = $(row).detach();
       } else {
            $(row).addClass("notdisplayed");
            others.push($(row).detach());
        }
    });

    exports.stream_name_match_stream_ids.sort(sort_by_stream_name);
    exports.stream_description_match_stream_ids.sort(sort_by_stream_name);

    _.each(exports.stream_name_match_stream_ids, function (stream_id) {
        $('#subscriptions_table .streams-list').append(widgets[stream_id]);
    });

    _.each(exports.stream_description_match_stream_ids, function (stream_id) {
        $('#subscriptions_table .streams-list').append(widgets[stream_id]);
    });

    $('#subscriptions_table .streams-list').append(others);

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

function redraw_privacy_related_stuff(sub_row, sub) {
    var stream_settings = settings_for_sub(sub);
    var html;

    sub = stream_data.add_admin_options(sub);

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

    stream_list.redraw_stream_privacy(sub.name);
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

var filter_streams = _.throttle(actually_filter_streams, 50);

exports.setup_page = function (callback) {
    function initialize_components() {
        var stream_filter_toggle = components.toggle({
            name: "stream-filter-toggle",
            selected: 0,
            values: [
                { label: i18n.t("Subscribed") },
                { label: i18n.t("All streams") },
            ],
            callback: function () {
                actually_filter_streams();
                remove_temporarily_miscategorized_streams();
            },
        }).get();

        if (should_list_all_streams()) {
            $("#subscriptions_table .search-container").prepend(stream_filter_toggle);
        }

        // show the "Stream settings" header by default.
        $(".display-type #stream_settings_title").show();
    }

    function _populate_and_fill() {
        var sub_rows = stream_data.get_streams_for_settings_page();

        $('#subscriptions_table').empty();

        var template_data = {
            can_create_streams: page_params.can_create_streams,
            subscriptions: sub_rows,
            hide_all_streams: !should_list_all_streams(),
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
        keep: keep,
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

exports.change_state = (function () {
    var prevent_next = false;

    var func = function (hash) {
        if (prevent_next) {
            prevent_next = false;
            return;
        }

        // if there are any arguments the state should be modified.
        if (hash.arguments.length > 0) {
            // if in #streams/new form.
            if (hash.arguments[0] === "new") {
                exports.new_stream_clicked();
                components.toggle.lookup("stream-filter-toggle").goto("All streams");
            } else if (hash.arguments[0] === "all") {
                components.toggle.lookup("stream-filter-toggle").goto("All streams");
            } else if (hash.arguments[0] === "subscribed") {
                components.toggle.lookup("stream-filter-toggle").goto("Subscribed");
            // if the first argument is a valid number.
            } else if (/\d+/.test(hash.arguments[0])) {
                var $stream_row = $(".stream-row[data-stream-id='" + hash.arguments[0] + "']");
                var top = $stream_row.click()[0].offsetTop;

                $(".streams-list").animate({ scrollTop: top }, 200);
            }
        }
    };

    func.prevent_once = function () {
        prevent_next = true;
    };

    return func;
}());

exports.launch = function (hash) {
    meta.is_open = true;
    exports.setup_page(function () {
        $("#subscription_overlay").addClass("show");

        exports.change_state(hash);
    });
};

Object.defineProperty(exports, "is_open", {
    get: function () {
        return meta.is_open;
    },
    enumerable: false,
});

exports.close = function () {
    hashchange.exit_modal();
    meta.is_open = false;
    subs.remove_miscategorized_streams();
};

exports.switch_rows = function (event) {
    var active_data = get_active_data();
    var switch_row;
    if (!active_data.id || active_data.row.hasClass('notdisplayed')) {
        switch_row = $('div.stream-row:not(.notdisplayed):first');
    } else if (event === 'up_arrow') {
        switch_row = active_data.row.prev();
    } else if (event === 'down_arrow') {
        switch_row = active_data.row.next();
        if ($('#search_stream_name').is(":focus")) {
            $('#search_stream_name').blur();
            return;
        }
    }

    var row_data = get_row_data(switch_row);
    if (row_data && !switch_row.hasClass('notdisplayed')) {
        var switch_row_name = row_data.object.name;
        var hash = ['#streams', row_data.id, switch_row_name];
        export_hash(hash);
    } else if (event === 'up_arrow' && !row_data) {
        $('#search_stream_name').focus();
    }
};

exports.keyboard_sub = function () {
    var active_data = get_active_data();
    var row_data = get_row_data(active_data.row);
    if (row_data) {
        subs.sub_or_unsub(row_data.object);
        if (row_data.object.subscribed && active_data.tab.text() === 'Subscribed') {
            active_data.row.addClass('notdisplayed');
            active_data.row.removeClass('active');
        }
    }
};

exports.toggle_view = function (event) {
    var active_data = get_active_data();
    var hash;
    if (event === 'right_arrow' && active_data.tab.text() === 'Subscribed') {
        hash = ['#streams', 'all'];
        export_hash(hash);
    } else if (event === 'left_arrow' && active_data.tab.text() === 'All streams') {
        hash = ['#streams', 'subscribed'];
        export_hash(hash);
    }
};

exports.view_stream = function () {
    var active_data = get_active_data();
    var row_data = get_row_data(active_data.row);
    if (row_data) {
        window.location.hash = '#narrow/stream/' + row_data.object.name;
    }
};

function ajaxSubscribe(stream) {
    // Subscribe yourself to a single stream.
    var true_stream_name;

    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([{name: stream}]) },
        success: function (resp, statusText, xhr) {
            if (subs.is_open) {
                $("#create_stream_name").val("");

                actually_filter_streams();
            }

            var res = JSON.parse(xhr.responseText);
            if (!$.isEmptyObject(res.already_subscribed)) {
                // Display the canonical stream capitalization.
                true_stream_name = res.already_subscribed[people.my_current_email()][0];
                ui_report.success(i18n.t("Already subscribed to __stream__", {stream: true_stream_name}),
                                  $("#subscriptions-status"), 'subscriptions-status');
            }
            // The rest of the work is done via the subscribe event we will get
        },
        error: function (xhr) {
            ui_report.error(i18n.t("Error adding subscription"), xhr,
                            $("#subscriptions-status"), 'subscriptions-status');
        },
    });
}

function ajaxUnsubscribe(sub) {
    // TODO: use stream_id when backend supports it
    return channel.del({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([sub.name]) },
        success: function () {
            $("#subscriptions-status").hide();
            // The rest of the work is done via the unsubscribe event we will get
        },
        error: function (xhr) {
            ui_report.error(i18n.t("Error removing subscription"), xhr,
                            $("#subscriptions-status"), 'subscriptions-status');
        },
    });
}

function ajaxSubscribeForCreation(stream, description, principals, invite_only, announce) {
    // Subscribe yourself and possible other people to a new stream.
    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([{name: stream, description: description}]),
               principals: JSON.stringify(principals),
               invite_only: JSON.stringify(invite_only),
               announce: JSON.stringify(announce),
        },
        success: function () {
            $("#create_stream_name").val("");
            $("#create_stream_description").val("");
            $("#subscriptions-status").hide();
            // The rest of the work is done via the subscribe event we will get
        },
        error: function (xhr) {
            ui_report.error(i18n.t("Error creating stream"), xhr,
                            $("#subscriptions-status"), 'subscriptions-status');
        },
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
        streams: stream_data.get_streams_for_settings_page(),
    }));

    // Make the options default to the same each time:
    // public, "announce stream" on.
    $('#make-invite-only input:radio[value=public]').prop('checked', true);
    $('#announce-new-stream input').prop('disabled', false);
    $('#announce-new-stream input').prop('checked', true);

    $("#stream_name_error").hide();

    $("#stream-checkboxes label.checkbox").on('change', function (e) {
        var elem = $(this);
        var stream_id = elem.attr('data-stream-id');
        var checked = elem.find('input').prop('checked');
        var subscriber_ids = stream_data.get_sub_by_id(stream_id).subscribers;

        $('#user-checkboxes label.checkbox').each(function () {
            var user_elem = $(this);
            var user_id = user_elem.attr('data-user-id');

            if (subscriber_ids.has(user_id)) {
                user_elem.find('input').prop('checked', checked);
            }
        });

        update_announce_stream_state();
        e.preventDefault();
    });
}

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

exports.sub_or_unsub = function (sub) {
    if (sub.subscribed) {
        ajaxUnsubscribe(sub);
    } else {
        ajaxSubscribe(sub.name);
    }
};

exports.new_stream_clicked = function () {
    var stream = $.trim($("#search_stream_name").val());

    if (!should_list_all_streams()) {
        // Realms that don't allow listing streams should simply be subscribed to.
        meta.stream_created = stream;
        ajaxSubscribe($("#search_stream_name").val());
        return;
    }

    // this changes the tab switcher (settings/preview) which isn't necessary
    // to a add new stream title.
    $(".display-type #add_new_stream_title").show();
    $(".display-type #stream_settings_title").hide();

    $(".stream-row.active").removeClass("active");

    $("#stream_settings_title, .subscriptions-container .settings, .nothing-selected").hide();
    $("#stream-creation, #add_new_stream_title").show();

    $('#create_stream_name').val(stream);
    show_new_stream_modal();

    // at less than 700px we have a @media query that when you tap the
    // #create_stream_button, the stream prompt slides in. However, when you
    // focus  the button on that page, the entire app view jumps over to
    // the other tab, and the animation breaks.
    // it is unclear whether this is a browser bug or "feature", however what
    // is clear is that this shoudn't be touched unless you're also changing
    // the mobile @media query at 700px.
    if (window.innerWidth > 700) {
        $('#create_stream_name').focus();
    }

    // change the hash to #streams/new to allow for linking and
    // easy discovery.

    window.location.hash = "#streams/new";
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
        settings: function () {
            $(".settings, #stream_settings_title").show();
            $("#add_new_stream_title, #stream-creation, .nothing-selected").hide();
        },
    };

    $("#subscriptions_table").on("click", "#create_stream_button", function (e) {
        e.preventDefault();
        exports.new_stream_clicked();
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

    // 'Check all' and 'Uncheck all' visible users
    $(document).on('click', '.subs_set_all_users', function (e) {
        $('#user-checkboxes .checkbox').each(function (idx, li) {
            if  (li.style.display !== "none") {
                $(li.firstElementChild).prop('checked', true);
            }
        });
        e.preventDefault();
        update_announce_stream_state();
    });
    $(document).on('click', '.subs_unset_all_users', function (e) {
        $('#user-checkboxes .checkbox').each(function (idx, li) {
            if  (li.style.display !== "none") {
                $(li.firstElementChild).prop('checked', false);
            }
        });
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
        var user_list = $(".add-user-list-filter");
        if (user_list === 0) {
            return;
        }
        var search_term = user_list.expectOne().val().trim();
        var search_terms = search_term.toLowerCase().split(",");

        (function filter_user_checkboxes() {
            var user_labels = $("#user-checkboxes label.add-user-label");

            if (search_term === '') {
                user_labels.css({display: 'block'});
                return;
            }

            var users = people.get_rest_of_realm();
            var filtered_users = people.filter_people_by_search_terms(users, search_terms);

            // Be careful about modifying the follow code.  A naive implementation
            // will work very poorly with a large user population (~1000 users).
            //
            // I tested using: `./manage.py populate_db --extra-users 3500`
            //
            // This would break the previous implementation, whereas the new
            // implementation is merely sluggish.
            user_labels.each(function () {
                var elem = $(this);
                var user_id = elem.attr('data-user-id');
                var user_checked = filtered_users.has(user_id);
                var display = user_checked ? "block" : "none";
                elem.css({display: display});
            });
        }());

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
            var stream_status = exports.check_stream_existence(stream);

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

            // You are always subscribed to streams you create.
            principals.push(people.my_current_email());

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

    function setup_subscriptions_stream_hash(sub, stream_id) {
        exports.change_state.prevent_once();
        window.location.hash = "#streams" + "/" +
            stream_id + "/" +
            hash_util.encodeHashComponent(sub.name);
    }

    function show_stream_row(node, show_settings) {
        $(".display-type #add_new_stream_title").hide();
        $(".display-type #stream_settings_title, .right .settings").show();
        $(".stream-row.active").removeClass("active");
        if (show_settings) {
            show_subs_pane.settings();

            $(node).addClass("active");
            exports.show_settings_for(get_stream_id(node));
        } else {
            show_subs_pane.nothing_selected();
        }
    }

    $("#subscriptions_table").on("click", ".sub_unsub_button", function (e) {
        var sub = get_sub_for_target(e.target);
        var stream_row = $(this).parent();
        var stream_id = stream_row.attr("data-stream-id");
        exports.sub_or_unsub(sub);
        var sub_settings = settings_for_sub(sub);
        var regular_sub_settings = sub_settings.find(".regular_subscription_settings");
        if (!sub.subscribed) {
            regular_sub_settings.addClass("in");
            show_stream_row(stream_row, true);
        } else {
            regular_sub_settings.removeClass("in");
        }

        setup_subscriptions_stream_hash(sub, stream_id);
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
        exports.sub_or_unsub(sub);
    });

    $('.empty_feed_sub_unsub').click(function (e) {
        e.preventDefault();

        $('#subscription-status').hide();
        var stream_name = narrow.stream();
        if (stream_name === undefined) {
            return;
        }
        var sub = stream_data.get_sub(stream_name);
        exports.sub_or_unsub(sub);

        $('.empty_feed_notice').hide();
        $('#empty_narrow_message').show();
    });

    $("#subscriptions_table").on("click", ".stream-row, #create_stream_button", function () {
        $(".right").addClass("show");
        $(".subscriptions-header").addClass("slide-left");
    });

    $("#subscriptions_table").on("click", ".icon-vector-chevron-left", function () {
        $(".right").removeClass("show");
        $(".subscriptions-header").removeClass("slide-left");
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

    $("#subscriptions_table").on("click", ".stream-row", function (e) {
        if ($(e.target).closest(".check, .subscription_settings").length === 0) {
            show_stream_row(this, true);
            var stream_id = $(this).attr("data-stream-id");
            var sub = stream_data.get_sub_by_id(stream_id);
            setup_subscriptions_stream_hash(sub, stream_id);
        }
    });

    (function defocus_sub_settings() {
        var sel = ".search-container, .streams-list, .subscriptions-header";

        $("#subscriptions_table").on("click", sel, function (e) {
            if ($(e.target).is(sel)) {
                show_stream_row(this, false);
            }
        });
    }());

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
    ui_util.change_tab_to("#streams");
};

// *Synchronously* check if a stream exists.
// This is deprecated and we hope to remove it.
exports.check_stream_existence = function (stream_name, autosubscribe) {
    var result = "error";
    var request = {stream: stream_name};
    if (autosubscribe) {
        request.autosubscribe = true;
    }
    channel.post({
        url: "/json/subscriptions/exists",
        data: request,
        async: false,
        success: function (data) {
            if (data.subscribed) {
                result = "subscribed";
            } else {
                result = "not-subscribed";
            }
        },
        error: function (xhr) {
            if (xhr.status === 404) {
                result = "does-not-exist";
            } else {
                result = "error";
            }
        },
    });
    return result;
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = subs;
}
