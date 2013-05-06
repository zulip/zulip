var subs = (function () {

var exports = {};

var stream_info = {}; // Maps lowercase stream name to stream properties object
// We fetch the stream colors asynchronous while the message feed is
// getting constructed, so we may need to go back and color streams
// that have already been rendered.
var initial_color_fetch = true;

var default_color = "#c2c2c2";
// Auto-assigned colors should be from the default palette so it's easy to undo
// changes, so if that pallete changes, change these colors.
var stream_assignment_colors = ["#76ce90", "#fae589", "#a6c7e5", "#e79ab5",
                                "#bfd56f", "#f4ae55", "#b0a5fd", "#addfe5",
                                "#f5ce6e", "#c2726a", "#94c849", "#bd86e5",
                                "#ee7e4a", "#a6dcbf", "#95a5fd", "#53a063",
                                "#9987e1", "#e4523d", "#c2c2c2", "#4f8de4",
                                "#c6a8ad", "#e7cc4d", "#c8bebf", "#a47462"];

// Clone stream_assignement_colors
var available_colors = stream_assignment_colors.slice(0);

var next_sub_id = 0;

function add_sub(stream_name, sub) {
    stream_info[stream_name.toLowerCase()] = sub;
}

function get_sub(stream_name) {
    return stream_info[stream_name.toLowerCase()];
}

// Classes which could be returned by get_color_class.
exports.color_classes = 'dark_background';

function pick_color() {
    if (available_colors.length === 0) {
        // We've used all the palette colors, so start re-using them.
        return stream_assignment_colors[exports.subscribed_streams().length
                                        % stream_assignment_colors.length];
    }

    return available_colors[0];
}

function mark_color_used(color) {
    var i;
    for (i = 0; i < available_colors.length; ++i) {
        if (available_colors[i] === color) {
            available_colors.splice(i, 1);
            return;
        }
    }
}

exports.subscribed_streams = function () {
    // TODO: Object.keys() compatibility
    var list = [];
    $.each(Object.keys(stream_info), function (idx, key) {
        var sub = stream_info[key];
        if (sub.subscribed) {
            list.push(sub.name);
        }
    });
    list.sort();
    return list;
};

exports.maybe_toggle_all_messages = function () {
    var show_all_messages = false;
    $.each(stream_info, function (idx, stream) {
        if (!stream.in_home_view) {
            show_all_messages = true;
            return false;
        }
    });

    var all_messages = $("#global_filters [data-name='all']")[0];
    if (!show_all_messages) {
        $(all_messages).addClass('hidden-filter');
    } else {
        $(all_messages).removeClass('hidden-filter');
    }
};

function should_render_subscribers() {
    return page_params.domain !== 'mit.edu';
}

function should_list_all_streams() {
    return page_params.domain !== 'mit.edu';
}

function update_table_stream_color(table, stream_name, color) {
    var color_class = exports.get_color_class(color);
    function fixup(elem) {
        elem.css("background-color", color)
            .removeClass(exports.color_classes)
            .addClass(color_class);
    }

    $.each(table.find(".stream_label"), function () {
        if ($(this).text() === stream_name) {
            var parent_label = $(this).parent("td");
            fixup(parent_label);
            fixup(parent_label.prev("td"));
        }
    });
}

exports.stream_id = function(stream_name) {
    var sub = get_sub(stream_name);
    if (sub === undefined) {
        blueslip.error("Tried to get subs.stream_id for a stream user is not subscribed to!");
        return 0;
    }
    return parseInt(sub.id, 10);
};

function update_stream_sidebar_swatch_color(stream_name, color) {
    var id = exports.stream_id(stream_name);
    $("#stream_sidebar_swatch_" + id).css('background-color', color);
}

function update_historical_message_color(stream_name, color) {
    update_table_stream_color($(".focused_table"), stream_name, color);
    if ($(".focused_table").attr("id") !== "#zhome") {
        update_table_stream_color($("#zhome"), stream_name, color);
    }
}

function update_stream_color(stream_name, color, opts) {
    opts = $.extend({}, {update_historical: false}, opts);
    var sub = get_sub(stream_name);
    sub.color = color;
    var id = parseInt(sub.id, 10);
    $("#subscription_" + id + " .color_swatch").css('background-color', color);
    if (opts.update_historical) {
        update_historical_message_color(stream_name, color);
    }
    update_stream_sidebar_swatch_color(stream_name, color);
}

function set_stream_property(stream_name, property, value) {
    $.ajax({
        type:     'POST',
        url:      '/json/subscriptions/property',
        dataType: 'json',
        data: {
            "property": property,
            "stream_name": stream_name,
            "value": value
        },
        timeout:  10*1000
    });
}

function stream_home_view_clicked(e) {
    var sub_row = $(e.target).closest('.subscription_row');
    var stream = sub_row.find('.subscription_name').text();

    var sub = get_sub(stream);
    sub.in_home_view = ! sub.in_home_view;

    setTimeout(function () {
        home_msg_list.clear({clear_selected_id: false});

        // Remember the scroll position as the adding or removing this
        // number of rows might cause the page to scroll in unexpected ways
        var saved_ypos = window.scrollY;

        // Recreate the home_msg_list with the newly filtered all_msg_list
        add_messages(all_msg_list.all(), home_msg_list);

        // Ensure we're still at the same scroll position
        window.scrollTo(0, saved_ypos);

        // In case we added messages to what's visible in the home view, we need to re-scroll to make
        // sure the pointer is still visible. We don't want the auto-scroll handler to move our pointer
        // to the old scroll location before we have a chance to update it.
        recenter_pointer_on_display = true;
        suppress_scroll_pointer_update = true;

        if (! home_msg_list.empty()) {
            process_loaded_for_unread(home_msg_list.all());
        }
    }, 0);

    exports.maybe_toggle_all_messages();
    set_stream_property(stream, 'in_home_view', sub.in_home_view);
}

function stream_notifications_clicked(e) {
    var sub_row = $(e.target).closest('.subscription_row');
    var stream = sub_row.find('.subscription_name').text();

    var sub = get_sub(stream);
    sub.notifications = ! sub.notifications;
    set_stream_property(stream, 'notifications', sub.notifications);
}

function set_color(stream_name, color) {
    update_stream_color(stream_name, color, {update_historical: true});
    set_stream_property(stream_name, 'color', color);
}

var colorpicker_options = {
    clickoutFiresChange: true,
    showPalette: true,
    palette: [
        ['a47462', 'c2726a', 'e4523d', 'e7664d', 'ee7e4a', 'f4ae55'],
        ['76ce90', '53a063', '94c849', 'bfd56f', 'fae589', 'f5ce6e'],
        ['a6dcbf', 'addfe5', 'a6c7e5', '4f8de4', '95a5fd', 'b0a5fd'],
        ['c2c2c2', 'c8bebf', 'c6a8ad', 'e79ab5', 'bd86e5', '9987e1']
    ],
    change: function (color) {
        // TODO: Kind of a hack.
        var sub_row = $(this).closest('.subscription_row');
        var stream_name = sub_row.find('.subscription_name').text();
        var hex_color = color.toHexString();
        set_color(stream_name, hex_color);
    }
};

function create_sub(stream_name, attrs) {
    var sub = get_sub(stream_name);
    if (sub !== undefined) {
        // We've already created this subscription, no need to continue.
        return sub;
    }

    sub = $.extend({}, {name: stream_name, id: next_sub_id++,
                        render_subscribers: should_render_subscribers(),
                        subscribed: true, in_home_view: true, invite_only: false,
                        notifications: false}, attrs);
    if (sub.color === undefined) {
        sub.color = pick_color();
    }
    mark_color_used(sub.color);

    add_sub(stream_name, sub);
    $(document).trigger($.Event('sub_obj_created.zephyr', {sub: sub}));
    if (sub.subscribed) {
        stream_list.add_narrow_filter(stream_name, "stream");
    }
    return sub;
}

function button_for_sub(sub) {
    var id = parseInt(sub.id, 10);
    return $("#subscription_" + id + " .sub_unsub_button");
}

function settings_for_sub(sub) {
    var id = parseInt(sub.id, 10);
    return $("#subscription_settings_" + id);
}

function add_sub_to_table(sub) {
    $('#create_stream_row').after(
        templates.render('subscription', {subscriptions: [sub]}));
    settings_for_sub(sub).collapse('show');
}

function format_member_list_elem(name, email) {
    return name + ' <' + email + '>';
}

function add_to_member_list(ul, name, email) {
    var member;
    if (email === undefined) {
        member = name;
    } else {
        member = format_member_list_elem(name, email);
    }
    $('<li>').prependTo(ul).text(member);
}

function mark_subscribed(stream_name, attrs) {
    var sub = get_sub(stream_name);

    if (sub === undefined) {
        // Create a new stream.
        sub = create_sub(stream_name, attrs);
        add_sub_to_table(sub);
    } else if (! sub.subscribed) {
        // Add yourself to an existing stream.
        sub.subscribed = true;
        set_color(stream_name, pick_color());
        mark_color_used(sub.color);
        stream_list.add_narrow_filter(stream_name, "stream");
        var settings = settings_for_sub(sub);
        var button = button_for_sub(sub);
        if (button.length !== 0) {
            button.text("Unsubscribe").removeClass("btn-primary");
            // Add the user to the member list if they're currently
            // viewing the members of this stream
            if (sub.render_subscribers && settings.hasClass('in')) {
                var members = settings.find(".subscriber_list_container ul");
                add_to_member_list(members, page_params.fullname, page_params.email);
            }
        } else {
            add_sub_to_table(sub);
        }

        // Display the swatch and subscription settings
        var sub_row = settings.closest('.subscription_row');
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
    process_loaded_for_unread(all_msg_list.all());
    stream_list.sort_narrow_list();

    typeahead_helper.update_autocomplete();

    $(document).trigger($.Event('subscription_add_done.zephyr', {sub: sub}));
}

function mark_unsubscribed(stream_name) {
    var sub = get_sub(stream_name);

    if (sub === undefined) {
        // We don't know about this stream
        return;
    } else if (sub.subscribed) {
        stream_list.remove_narrow_filter(stream_name, 'stream');
        sub.subscribed = false;
        button_for_sub(sub).text("Subscribe").addClass("btn-primary");
        var settings = settings_for_sub(sub);
        if (settings.hasClass('in')) {
            settings.collapse('hide');
        }

        // Hide the swatch and subscription settings
        var sub_row = settings.closest('.subscription_row');
        sub_row.find(".color_swatch").removeClass('in');
        if (sub.render_subscribers) {
            // TODO: having a completely empty settings div messes
            // with Bootstrap's collapser.  We currently just ensure
            // that it's not empty on the MIT realm, even though it
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

    typeahead_helper.update_autocomplete();

    $(document).trigger($.Event('subscription_remove_done.zephyr', {sub: sub}));
}

$(function () {
    $(document).on('subscription_add.zephyr', function (e) {
        mark_subscribed(e.subscription.name, e.subscription);
    });
    $(document).on('subscription_remove.zephyr', function (e) {
        mark_unsubscribed(e.subscription.name);
    });

    $(document).on('click', '.subs_set_all_users', function (e) {
        $('#people_to_add :checkbox').attr('checked', true);
        e.preventDefault();
    });
    $(document).on('click', '.subs_unset_all_users', function (e) {
        $('#people_to_add :checkbox').attr('checked', false);
        e.preventDefault();
    });
});

exports.get_color = function (stream_name) {
    var sub = get_sub(stream_name);
    if (sub === undefined) {
        return default_color;
    }
    return sub.color;
};

var lightness_threshold;
$(function () {
    // sRGB color component for dark label text.
    // 0x33 to match the color #333333 set by Bootstrap.
    var label_color = 0x33;
    var lightness = colorspace.luminance_to_lightness(
        colorspace.sRGB_to_linear(label_color));

    // Compute midpoint lightness between that and white (100).
    lightness_threshold = (lightness + 100) / 2;
});

// From a background color (in format "#fff" or "#ffffff")
// pick a CSS class (or empty string) to determine the
// text label color etc.
//
// It would be better to work with an actual data structure
// rather than a hex string, but we have to deal with values
// already saved on the server, etc.
//
// This gets called on every message, so cache the results.
exports.get_color_class = util.memoize(function (color) {
    var match, i, lightness, channel = [0, 0, 0], mult = 1;

    match = /^#([\da-fA-F]{2})([\da-fA-F]{2})([\da-fA-F]{2})$/.exec(color);
    if (!match) {
        // 3-digit shorthand; Spectrum gives this e.g. for pure black.
        // Multiply each digit by 16+1.
        mult = 17;

        match = /^#([\da-fA-F])([\da-fA-F])([\da-fA-F])$/.exec(color);
        if (!match) {
            // Can't understand color.
            return '';
        }
    }

    // CSS colors are specified in the sRGB color space.
    // Convert to linear intensity values.
    for (i=0; i<3; i++) {
        channel[i] = colorspace.sRGB_to_linear(mult * parseInt(match[i+1], 16));
    }

    // Compute perceived lightness as CIE L*.
    lightness = colorspace.luminance_to_lightness(
        colorspace.rgb_luminance(channel));

    // Determine if we're past the midpoint between the
    // dark and light label lightness.
    return (lightness < lightness_threshold) ? 'dark_background' : '';
});

exports.get_invite_only = function (stream_name) {
    var sub = get_sub(stream_name);
    if (sub === undefined) {
        return false;
    }
    return sub.invite_only;
};

exports.receives_notifications = function (stream_name) {
    var sub = get_sub(stream_name);
    if (sub === undefined) {
        return false;
    }
    return sub.notifications;
};

function populate_subscriptions(subs) {
    var sub_rows = [];
    subs.sort(function (a, b) {
        return util.strcmp(a.name, b.name);
    });
    subs.forEach(function (elem) {
        var stream_name = elem.name;
        var sub = create_sub(stream_name, {color: elem.color, in_home_view: elem.in_home_view,
                                           invite_only: elem.invite_only,
                                           notifications: elem.notifications, subscribed: true});
        sub_rows.push(sub);
    });

    stream_list.sort_narrow_list();
    return sub_rows;
}

exports.reload_subscriptions = function (opts) {
    var on_success;
    opts = $.extend({}, {clear_first: false, custom_callbacks: false}, opts);

    if (! opts.custom_callbacks) {
        on_success = function (data) {
                         if (data) {
                             populate_subscriptions(data.subscriptions);
                         }
                     };
    }

    if (opts.clear_first) {
        stream_info = {};
        stream_list.remove_all_narrow_filters();
    }

    return $.ajax({
                    type:     'POST',
                    url:      '/json/subscriptions/list',
                    dataType: 'json',
                    timeout:  10*1000,
                    success: on_success
    });
};

exports.setup_page = function () {
    util.make_loading_indicator($('#subs_page_loading_indicator'));

    function populate_and_fill(stream_data, subscription_data) {
        var all_streams = [];
        var our_subs = [];

        /* arguments are [ "success", statusText, jqXHR ] */
        if (stream_data.length > 2 && stream_data[2]) {
            var stream_response = JSON.parse(stream_data[2].responseText);
            all_streams = stream_response.streams;
        }
        if (subscription_data.length > 2 && subscription_data[2]) {
            var subs_response = JSON.parse(subscription_data[2].responseText);
            our_subs = subs_response.subscriptions;
        }

        var sub_rows = populate_subscriptions(our_subs);

        all_streams.sort();
        all_streams.forEach(function (stream) {
            if (exports.have(stream)) {
                return;
            }
            var sub = create_sub(stream, {subscribed: false});
            sub_rows.push(sub);
        });

        $('#subscriptions_table tr:gt(0)').remove();
        $('#subscriptions_table').append(
            templates.render('subscription', {subscriptions: sub_rows}));

        util.destroy_loading_indicator($('#subs_page_loading_indicator'));
        $('#create_stream_name').focus().select();
    }

    function failed_listing(xhr, error) {
        util.destroy_loading_indicator($('#subs_page_loading_indicator'));
        ui.report_error("Error listing streams or subscriptions", xhr, $("#subscriptions-status"));
    }

    var requests = [];
    if (should_list_all_streams()) {
        // This query must go first to prevent a race when we are not
        // listing all streams
        var req = $.ajax({
            type:     'POST',
            url:      '/json/get_public_streams',
            dataType: 'json',
            timeout:  10*1000
        });
        requests.push(req);
    } else {
        // Handing an object to $.when() means that it counts as a 'success' with the
        // object delivered directly to the callback
        requests.push({streams: []});
        $('#create_stream_button').val("Subscribe");
    }

    requests.push(exports.reload_subscriptions({custom_callbacks: true}));

    // Trigger finished callback when:
    // * Both AJAX requests are finished, if we sent themm both
    // * Just one AJAX is finished if should_list_all_streams() is false
    $.when.apply(this, requests).then(populate_and_fill, failed_listing);
};

exports.have = function (stream_name) {
    var sub = get_sub(stream_name);
    if (sub !== undefined && sub.subscribed) {
        return sub;
    }
    return false;
};

function ajaxSubscribe(stream) {
    // Subscribe yourself to a single stream.
    var true_stream_name;

    return $.ajax({
        type: "POST",
        url: "/json/subscriptions/add",
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        data: {"subscriptions": JSON.stringify([stream]) },
        success: function (resp, statusText, xhr, form) {
            $("#create_stream_name").val("");

            var res = $.parseJSON(xhr.responseText);
            if (!$.isEmptyObject(res.already_subscribed)) {
                // Display the canonical stream capitalization.
                true_stream_name = res.already_subscribed[page_params.email][0];
                ui.report_success("Already subscribed to " + true_stream_name,
                                  $("#subscriptions-status"));
            }
            // The rest of the work is done via the subscribe event we will get
        },
        error: function (xhr) {
            ui.report_error("Error adding subscription", xhr, $("#subscriptions-status"));
            $("#create_stream_name").focus();
        }
    });
}

function ajaxUnsubscribe(stream) {
    $.ajax({
        type: "POST",
        url: "/json/subscriptions/remove",
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        data: {"subscriptions": JSON.stringify([stream]) },
        success: function (resp, statusText, xhr, form) {
            var name, res = $.parseJSON(xhr.responseText);
            $("#subscriptions-status").hide();
            // The rest of the work is done via the unsubscribe event we will get
        },
        error: function (xhr) {
            ui.report_error("Error removing subscription", xhr, $("#subscriptions-status"));
            $("#create_stream_name").focus();
        }
    });
}

function ajaxSubscribeForCreation(stream, principals, invite_only) {
    // Subscribe yourself and possible other people to a new stream.
    return $.ajax({
        type: "POST",
        url: "/json/subscriptions/add",
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        data: {"subscriptions": JSON.stringify([stream]),
               "principals": JSON.stringify(principals),
               "invite_only": JSON.stringify(invite_only)
        },
        success: function (data) {
            $("#create_stream_name").val("");
            $("#subscriptions-status").hide();
            $('#stream-creation').modal("hide");
            // The rest of the work is done via the subscribe event we will get
        },
        error: function (xhr) {
            ui.report_error("Error creating stream", xhr, $("#subscriptions-status"));
            $('#stream-creation').modal("hide");
        }
    });
}

// The tutorial bot needs this function to add you to the
// tutorial-yourname stream.
exports.tutorial_subscribe_or_add_me_to = function (stream_name) {
    var stream_status = compose.check_stream_existence(stream_name);
    if (stream_status === 'does-not-exist') {
        return ajaxSubscribeForCreation(stream_name, [page_params.email], false);
    } else {
        return ajaxSubscribe(stream_name);
    }
};

exports.tutorial_unsubscribe_me_from = function (stream_name) {
    ajaxUnsubscribe(stream_name);
};

function people_cmp(person1, person2) {
    // Compares objects of the form used in people_list.
    var name_cmp = util.strcmp(person1.full_name, person2.full_name);
    if (name_cmp < 0) {
        return -1;
    } else if (name_cmp > 0) {
        return 1;
    }
    return util.strcmp(person1.email, person2.email);
}

function show_new_stream_modal() {
    var people_minus_you_and_maybe_humbuggers = [];
    $.each(page_params.people_list, function (idx, person) {
        if (person.email !== page_params.email &&
               (page_params.domain === "humbughq.com" ||
                   person.email.split('@')[1] !== "humbughq.com"
               )
           ) {
            people_minus_you_and_maybe_humbuggers.push({"email": person.email,
                "full_name": person.full_name});
        }
    });

    $('#people_to_add').html(templates.render('new_stream_users', {
        users: people_minus_you_and_maybe_humbuggers.sort(people_cmp)
    }));
    $('#stream-creation').modal("show");
}

$(function () {
    var i;
    // Populate stream_info with data handed over to client-side template.
    populate_subscriptions(page_params.stream_list);

    $("#add_new_subscription").on("submit", function (e) {
        e.preventDefault();

        if (!should_list_all_streams()) {
            ajaxSubscribe($("#create_stream_name").val());
            return;
        }

        var stream = $.trim($("#create_stream_name").val());
        var stream_status = compose.check_stream_existence(stream);
        if (stream_status === "does-not-exist") {
            $("#stream_name").text(stream);
            show_new_stream_modal();
        } else {
            ajaxSubscribe(stream);
        }
    });

    $("#stream_creation_form").on("submit", function (e) {
        e.preventDefault();
        var stream = $.trim($("#create_stream_name").val());
        var principals = [];
        $("#stream_creation_form input:checkbox[name=user]:checked").each(function () {
            principals.push($(this).val());
        });
        // You are always subscribed to streams you create.
        principals.push(page_params.email);
        ajaxSubscribeForCreation(stream,
            principals,
            $('#stream_creation_form input[name=privacy]:checked').val() === "invite-only"
            );
    });

    $("#subscriptions_table").on("click", ".sub_unsub_button", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var sub_row = $(e.target).closest('.subscription_row');
        var stream_name = sub_row.find('.subscription_name').text();
        var sub = get_sub(stream_name);

        if (sub.subscribed) {
            ajaxUnsubscribe(stream_name);
        } else {
            ajaxSubscribe(stream_name);
        }
    });

    $("#subscriptions_table").on("show", ".subscription_settings", function (e) {
        var subrow = $(e.target).closest('.subscription_row');
        var colorpicker = subrow.find('.colorpicker');
        colorpicker.spectrum(colorpicker_options);

        // To figure out the worst case for an expanded row's height, we do some math:
        // .subscriber_list_container max-height,
        // .subscriber_list_settings,
        // .regular_subscription_settings
        // .subscription_header line-height,
        // .subscription_header padding
        var expanded_row_size = 200 + 30 + 100 + 30 + 5;
        var cover = subrow.position().top + expanded_row_size -
            viewport.height() + $("#top_navbar").height() - viewport.scrollTop();
        if (cover > 0) {
            $('html, body').animate({
                scrollTop: viewport.scrollTop() + cover + 5
            });
        }

    });

    $("#subscriptions_table").on("click", ".sub_setting_checkbox", function (e) {
        var control = $(e.target).closest('.sub_setting_checkbox').find('.sub_setting_control');
        // A hack.  Don't change the state of the checkbox if we
        // clicked on the checkbox itself.
        if (control[0] !== e.target) {
            control.prop("checked", ! control.prop("checked"));
        }
    });
    $("#subscriptions_table").on("click", "#sub_setting_in_home_view", stream_home_view_clicked);
    $("#subscriptions_table").on("click", "#sub_setting_notifications", stream_notifications_clicked);

    if (! should_render_subscribers()) {
        return;
    }

    // From here down is only stuff that happens when we're rendering
    // the subscriber settings

    $("#subscriptions_table").on("submit", ".subscriber_list_add form", function (e) {
        e.preventDefault();
        var sub_row = $(e.target).closest('.subscription_row');
        var stream = sub_row.find('.subscription_name').text();
        var text_box = sub_row.find('input[name="principal"]');
        var principal = $.trim(text_box.val());
        // TODO: clean up this error handling
        var error_elem = sub_row.find('.subscriber_list_container .alert-error');
        var warning_elem = sub_row.find('.subscriber_list_container .alert-warning');
        var list = sub_row.find('.subscriber_list_container ul');

        $.ajax({
            type: "POST",
            url: "/json/subscriptions/add",
            dataType: 'json',
            data: {"subscriptions": JSON.stringify([stream]),
                   "principals": JSON.stringify([principal])},
            success: function (data) {
                text_box.val('');

                if (data.subscribed.hasOwnProperty(principal)) {
                    error_elem.addClass("hide");
                    warning_elem.addClass("hide");
                    if (principal === page_params.email) {
                        // mark_subscribed adds the user to the member list
                        mark_subscribed(stream);
                    } else {
                        add_to_member_list(list, people_dict[principal].full_name, principal);
                    }
                } else {
                    error_elem.addClass("hide");
                    warning_elem.removeClass("hide").text("User already subscribed");
                }
            },
            error: function (xhr) {
                warning_elem.addClass("hide");
                error_elem.removeClass("hide").text("Could not add user to this stream");
            }
        });
    });

    $("#subscriptions_table").on("show", ".regular_subscription_settings", function (e) {
        // We want 'show' events that originate from
        // 'regular_subscription_settings' divs not to trigger the
        // handler for the entire subscription_settings div
        e.stopPropagation();
    });

    $("#subscriptions_table").on("show", ".subscription_settings", function (e) {
        var sub_row = $(e.target).closest('.subscription_row');
        var stream = sub_row.find('.subscription_name').text();
        var warning_elem = sub_row.find('.subscriber_list_container .alert-warning');
        var error_elem = sub_row.find('.subscriber_list_container .alert-error');
        var list = sub_row.find('.subscriber_list_container ul');
        var indicator_elem = sub_row.find('.subscriber_list_loading_indicator');

        warning_elem.addClass('hide');
        error_elem.addClass('hide');
        list.empty();

        util.make_loading_indicator(indicator_elem);

        $.ajax({
            type: "POST",
            url: "/json/get_subscribers",
            dataType: 'json', // This seems to be ignored. We still get back an xhr.
            data: {stream: stream},
            success: function (data) {
                util.destroy_loading_indicator(indicator_elem);
                var subscribers = $.map(data.subscribers, function (elem) {
                    var person = people_dict[elem];
                    if (person === undefined) {
                        return elem;
                    }
                    return format_member_list_elem(people_dict[elem].full_name, elem);
                });
                $.each(subscribers.sort().reverse(), function (idx, elem) {
                    // add_to_member_list *prepends* the element,
                    // so we need to sort in reverse order for it to
                    // appear in alphabetical order.
                    add_to_member_list(list, elem);
                });
            },
            error: function (xhr) {
                util.destroy_loading_indicator(indicator_elem);
                error_elem.removeClass("hide").text("Could not fetch subscriber list");
            }
        });

        sub_row.find('input[name="principal"]').typeahead({
            source: typeahead_helper.private_message_typeahead_list,
            items: 4,
            highlighter: function (item) {
                var query = this.query;
                return typeahead_helper.highlight_with_escaping(query, item);
            },
            matcher: function (item) {
                var query = $.trim(this.query);
                if (query === '') {
                    return false;
                }
                // Case-insensitive.
                return (item.toLowerCase().indexOf(query.toLowerCase()) !== -1);
            },
            updater: function (item) {
                return typeahead_helper.private_message_mapped[item].email;
            }
        });
    });
});

function focus_on_narrowed_stream() {
    var operators = narrow.operators();
    if (!operators) {
        return;
    }
    var stream_name = operators[0][1];
    var sub = get_sub(stream_name);
    if (sub !== undefined) {
        // This stream is in the list, so focus on it.
        $('html, body').animate({
            scrollTop: settings_for_sub(sub).offset().top
        });
    } else {
        // This stream doesn't exist, so prep for creating it.
        $("#create_stream_name").val(stream_name);
    }
}

exports.show_and_focus_on_narrow = function () {
    $("#gear-menu a[href='#subscriptions']").one('shown',
                                                 focus_on_narrowed_stream);
    ui.change_tab_to("#subscriptions");
};

return exports;

}());
