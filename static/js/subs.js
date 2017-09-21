var subs = (function () {

var meta = {
    callbacks: {},
};
var exports = {};

exports.show_subs_pane = {
    nothing_selected: function () {
        $(".nothing-selected, #stream_settings_title").show();
        $("#add_new_stream_title, .settings, #stream-creation").hide();
    },
    settings: function () {
        $(".settings, #stream_settings_title").show();
        $("#add_new_stream_title, #stream-creation, .nothing-selected").hide();
    },
};

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
    return !page_params.realm_is_zephyr_mirror_realm;
}

exports.toggle_home = function (sub) {
    stream_muting.update_in_home_view(sub, ! sub.in_home_view);
    stream_edit.set_stream_property(sub, 'in_home_view', sub.in_home_view);
};

exports.toggle_pin_to_top_stream = function (sub) {
    stream_edit.set_stream_property(sub, 'pin_to_top', !sub.pin_to_top);
};

exports.update_stream_name = function (sub, new_name) {
    // Rename the stream internally.
    stream_data.rename_sub(sub, new_name);
    var stream_id = sub.stream_id;

    // Update the left sidebar.
    stream_list.rename_stream(sub, new_name);

    // Update the stream settings
    stream_edit.update_stream_name(sub, new_name);

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
    stream_edit.update_stream_description(sub);
};

exports.set_color = function (stream_id, color) {
    var sub = stream_data.get_sub_by_id(stream_id);
    stream_edit.set_stream_property(sub, 'color', color);
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

// The `stream_create.get_name()` value tells us whether the stream was just
// created in this browser window; it's a hack to work around the
// server_events code flow not having a good way to associate with
// this request.  These should be appended to the top of the list so
// they are more visible.
function add_sub_to_table(sub) {
    stream_data.update_calculated_fields(sub);
    var html = templates.render('subscription', sub);
    var settings_html = templates.render('subscription_settings', sub);
    if (stream_create.get_name() === sub.name) {
        $(".streams-list").prepend(html).scrollTop(0);
    } else {
        $(".streams-list").append(html);
    }
    $(".subscriptions .settings").append($(settings_html));

    var email_address_hint_content = templates.render('email_address_hint', { page_params: page_params });
    add_email_hint(sub, email_address_hint_content);

    if (stream_create.get_name() === sub.name) {
        var created_stream = stream_create.get_name();
        $(".stream-row[data-stream-id='" + stream_data.get_sub(created_stream).stream_id + "']").click();
        stream_create.reset_created_stream();
    }
}

exports.remove_stream = function (stream_id) {
    // It is possible that row is empty when we deactivate a
    // stream, but we let jQuery silently handle that.
    var row = row_for_stream_id(stream_id);
    row.remove();
};

exports.update_settings_for_subscribed = function (sub) {
    var button = button_for_sub(sub);
    var settings_button = settings_button_for_sub(sub).removeClass("unsubscribed");

    if (button.length !== 0) {
        exports.rerender_subscribers_count(sub);

        button.toggleClass("checked");
        settings_button.text(i18n.t("Unsubscribe"));

        stream_edit.add_me_to_member_list(sub);
    } else {
        add_sub_to_table(sub);
    }

    // Display the swatch and subscription stream_settings
    stream_edit.show_sub(sub);
};

exports.update_settings_for_unsubscribed = function (sub) {
    var button = button_for_sub(sub);
    var settings_button = settings_button_for_sub(sub).addClass("unsubscribed");

    button.toggleClass("checked");
    settings_button.text(i18n.t("Subscribe"));

    exports.rerender_subscribers_count(sub);

    stream_edit.collapse(sub);

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
    var streams_list_scrolltop = $(".streams-list").scrollTop();

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

    ui.update_scrollbar($("#subscription_overlay .streams-list"));

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

    // this puts the scrollTop back to what it was before the list was updated again.
    $(".streams-list").scrollTop(streams_list_scrolltop);
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
            values: [
                { label: i18n.t("Subscribed"), key: "subscribed" },
                { label: i18n.t("All streams"), key: "all-streams" },
            ],
            callback: function (value, key) {
                // if you aren't on a particular stream (`streams/:id/:name`)
                // then redirect to `streams/all` when you click "all-streams".
                if (key === "all-streams") {
                    window.location.hash = "streams/all";
                } else if (key === "subscribed") {
                    window.location.hash = "streams/subscribed";
                }

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
                components.toggle.lookup("stream-filter-toggle").goto("all-streams");
            } else if (hash.arguments[0] === "all") {
                components.toggle.lookup("stream-filter-toggle").goto("all-streams");
            } else if (hash.arguments[0] === "subscribed") {
                components.toggle.lookup("stream-filter-toggle").goto("subscribed");
            // if the first argument is a valid number.
            } else if (/\d+/.test(hash.arguments[0])) {
                var stream_row = $(".stream-row[data-stream-id='" + hash.arguments[0] + "']");
                var streams_list = $(".streams-list")[0];

                get_active_data().row.removeClass("active");
                stream_row.addClass("active");

                if ($(".stream-row:not(.notdisplayed):first")[0] === stream_row[0]) {
                    streams_list.scrollTop = 0;
                }

                if ($(".stream-row:not(.notdisplayed):last")[0] === stream_row[0]) {
                    streams_list.scrollTop = streams_list.scrollHeight - $(".streams-list").height();
                }

                if (stream_row.position().top < 70) {
                    streams_list.scrollTop -= streams_list.clientHeight / 2;
                }

                var dist_from_top = stream_row.position().top;
                var total_dist = dist_from_top + stream_row[0].clientHeight;
                var dist_from_bottom = streams_list.clientHeight - total_dist;
                if (dist_from_bottom < -4) {
                    streams_list.scrollTop += streams_list.clientHeight / 2;
                }

                setTimeout(function () {
                    if (hash.arguments[0] === get_active_data().id) {
                        stream_row.click();
                    }
                }, 100);
            }
        }
    };

    func.prevent_once = function () {
        prevent_next = true;
    };

    return func;
}());

exports.launch = function (hash) {
    exports.setup_page(function () {
        overlays.open_overlay({
            name: 'subscriptions',
            overlay: $("#subscription_overlay"),
            on_close: exports.close,
        });
        exports.change_state(hash);

        ui.set_up_scrollbar($("#subscription_overlay .streams-list"));
        ui.set_up_scrollbar($("#subscription_overlay .settings"));

    });
    if (!get_active_data().id) {
        $('#search_stream_name').focus();
    }
};

exports.close = function () {
    hashchange.exit_overlay();
    subs.remove_miscategorized_streams();
};

exports.switch_rows = function (event) {
    var active_data = get_active_data();
    var switch_row;
    if (window.location.hash === '#streams/new') {
        // Prevent switching stream rows when creating a new stream
        return false;
    } else if (!active_data.id || active_data.row.hasClass('notdisplayed')) {
        switch_row = $('div.stream-row:not(.notdisplayed):first');
        if ($('#search_stream_name').is(":focus")) {
            $('#search_stream_name').blur();
        }
    } else {
        if (event === 'up_arrow') {
            switch_row = active_data.row.prevAll().not('.notdisplayed').first();
        } else if (event === 'down_arrow') {
            switch_row = active_data.row.nextAll().not('.notdisplayed').first();
        }
        if ($('#search_stream_name').is(":focus")) {
            // remove focus from Filter streams input instead of switching rows
            // if Filter streams input is focused
            return $('#search_stream_name').blur();
        }
    }

    var row_data = get_row_data(switch_row);
    if (row_data) {
        var switch_row_name = row_data.object.name;
        var hash = ['#streams', row_data.id, switch_row_name];
        export_hash(hash);
    } else if (event === 'up_arrow' && !row_data) {
        $('#search_stream_name').focus();
    }
    return true;
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
            if (overlays.streams_open()) {
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

exports.new_stream_clicked = function () {
    var stream = $.trim($("#search_stream_name").val());

    if (!should_list_all_streams()) {
        // Realms that don't allow listing streams should simply be subscribed to.
        stream_create.set_name(stream);
        ajaxSubscribe($("#search_stream_name").val());
        return;
    }

    stream_create.new_stream_clicked(stream);
};

exports.sub_or_unsub = function (sub) {
    if (sub.subscribed) {
        ajaxUnsubscribe(sub);
    } else {
        ajaxSubscribe(sub.name);
    }
};


$(function () {

    stream_data.initialize_from_page_params();
    stream_list.create_initial_sidebar_rows();

    // We build the stream_list now.  It may get re-built again very shortly
    // when new messages come in, but it's fairly quick.
    stream_list.build_stream_list();

    $("#subscriptions_table").on("click", "#create_stream_button", function (e) {
        e.preventDefault();
        exports.new_stream_clicked();
    });

    $(".subscriptions").on("click", "[data-dismiss]", function (e) {
        e.preventDefault();
        // we want to make sure that the click is not just a simulated
        // click; this fixes an issue where hitting "enter" would
        // trigger this code path due to bootstrap magic.
        if (e.clientY !== 0) {
            exports.show_subs_pane.nothing_selected();
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

    $('.empty_feed_sub_unsub').click(function (e) {
        e.preventDefault();

        $('#subscription-status').hide();
        var stream_name = narrow_state.stream();
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

    $("#subscriptions_table").on("click", ".fa-chevron-left", function () {
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

    (function defocus_sub_settings() {
        var sel = ".search-container, .streams-list, .subscriptions-header";

        $("#subscriptions_table").on("click", sel, function (e) {
            if ($(e.target).is(sel)) {
                stream_edit.show_stream_row(this, false);
            }
        });
    }());

    $("#subscriptions_table").on("hide", ".subscription_settings", function (e) {
        var sub_arrow = $(e.target).closest('.stream-row').find('.sub_arrow i');
        sub_arrow.removeClass('icon-vector-chevron-up');
        sub_arrow.addClass('icon-vector-chevron-down');
    });

    $(document).on('peer_subscribe.zulip', function (e, data) {
        var sub = stream_data.get_sub(data.stream_name);
        exports.rerender_subscribers_count(sub);
    });

    $(document).on('peer_unsubscribe.zulip', function (e, data) {
        var sub = stream_data.get_sub(data.stream_name);
        exports.rerender_subscribers_count(sub);
    });

});

function focus_on_narrowed_stream() {
    var stream_name = narrow_state.stream();
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

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = subs;
}
