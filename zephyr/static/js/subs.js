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
    var my_streams = exports.subscribed_streams();
    var used_colors = my_streams.map(function (stream_name) {
        return exports.get_color(stream_name);
    });

    var available_colors = stream_assignment_colors.filter(function (color) {
        return ($.inArray(color, used_colors) === -1);
    });

    if (available_colors.length === 0) {
        // We've used all the palette colors, so start re-using them.
        return stream_assignment_colors[my_streams.length % stream_assignment_colors.length];
    }

    return available_colors[0];
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
    return domain !== 'mit.edu';
}

function should_list_all_streams() {
    return domain !== 'mit.edu';
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

function stream_home_view_clicked(e) {
    var in_home_view, cb;
    if (e.target.type === "checkbox") {
        in_home_view = e.target.checked;
    } else {
        cb = $(e.target).closest('.sub_setting_show_in_home').children('.sub_setting_show_in_home_cb')[0];
        in_home_view = !cb.checked;
        $(cb).prop("checked", in_home_view);
    }

    var sub_row = $(e.target).closest('.subscription_row');
    var stream = sub_row.find('.subscription_name').text();

    if (in_home_view === undefined) {
        return;
    }

    var sub = get_sub(stream);
    sub.in_home_view = in_home_view;

    setTimeout(function () {
        home_msg_list.clear({clear_selected_id: false});

        // Remember the scroll position as the adding or removing this
        // number of rows might cause the page to scroll in unexpected ways
        var saved_ypos = window.scrollY;

        // Recreate the home_msg_list with the newly filtered all_msg_list
        add_messages(all_msg_list.all(), home_msg_list, {append_to_table: true, update_unread_counts: false});

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

    $.ajax({
        type:     'POST',
        url:      '/json/subscriptions/property',
        dataType: 'json',
        data: {
            "property": "in_home_view",
            "stream_name": stream,
            "in_home_view": in_home_view
        },
        timeout:  10*1000
    });
}

function set_color(stream_name, color) {
    update_stream_color(stream_name, color, {update_historical: true});

    $.ajax({
        type:     'POST',
        url:      '/json/subscriptions/property',
        dataType: 'json',
        data: {
            "property": "stream_colors",
            "stream_name": stream_name,
            "color": color
        },
        timeout:  10*1000
    });
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

    sub = $.extend({}, {name: stream_name, color: pick_color(), id: next_sub_id++,
                        render_subscribers: should_render_subscribers(),
                        subscribed: true, in_home_view: true, invite_only: false}, attrs);

    add_sub(stream_name, sub);
    if (sub.subscribed) {
        // This will do nothing on MIT
        ui.add_narrow_filter(stream_name, "stream", "#narrow/stream/" + encodeURIComponent(stream_name));
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
    $('#create_stream_row').after(templates.subscription({subscriptions: [sub]}));
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
        // This will do nothing on MIT
        ui.add_narrow_filter(stream_name, "stream", "#narrow/stream/" + encodeURIComponent(stream_name));
        var button = button_for_sub(sub);
        if (button.length !== 0) {
            button.text("Unsubscribe").removeClass("btn-primary");
        } else {
            add_sub_to_table(sub);
        }

        // Add the user to the member list if they're currently
        // viewing the members of this stream
        var settings = settings_for_sub(sub);
        if (sub.render_subscribers && settings.hasClass('in')) {
            var members = settings.find(".subscriber_list_container ul");
            add_to_member_list(members, fullname, email);
        }

        // Display the swatch and subscription settings
        var sub_row = settings.closest('.subscription_row');
        sub_row.find(".color_swatch").addClass('in');
        sub_row.find(".regular_subscription_settings").collapse('show');
    } else {
        // Already subscribed
        return;
    }

    // Update unread counts as the new stream in sidebar might
    // need its unread counts re-calculated
    process_loaded_for_unread(all_msg_list.all());

    typeahead_helper.update_autocomplete();
}

function mark_unsubscribed(stream_name) {
    var sub = get_sub(stream_name);

    ui.remove_narrow_filter(stream_name, 'stream');

    if (sub === undefined) {
        // We don't know about this stream
        return;
    } else if (sub.subscribed) {
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
    typeahead_helper.update_autocomplete();
}

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

exports.setup_page = function () {
    util.make_loading_indicator($('#subs_page_loading_indicator'));

    var our_subs;
    var all_streams;

    function maybe_populate_subscriptions() {
        // We only execute if both asynchronous queries have returned
        if (our_subs === undefined || all_streams === undefined) {
            return;
        }

        var sub_rows = [];
        our_subs.sort(function (a, b) {
            return a.name.localeCompare(b.name);
        });
        our_subs.forEach(function (elem) {
            var stream_name = elem.name;
            var sub = create_sub(stream_name, {color: elem.color, in_home_view: elem.in_home_view,
                                               invite_only: elem.invite_only, subscribed: true});
            add_sub(stream_name, sub);
            sub_rows.push(sub);
        });

        all_streams.sort();
        all_streams.forEach(function (stream) {
            if (exports.have(stream)) {
                return;
            }
            var sub = create_sub(stream, {subscribed: false});
            add_sub(stream, sub);
            sub_rows.push(sub);
        });

        $('#subscriptions_table tr:gt(0)').remove();
        $('#subscriptions_table').append(templates.subscription({subscriptions: sub_rows}));

        util.destroy_loading_indicator($('#subs_page_loading_indicator'));
        $('#create_stream_name').focus().select();
    }

    if (should_list_all_streams()) {
        // This query must go first to prevent a race when we are not
        // listing all streams
        $.ajax({
            type:     'POST',
            url:      '/json/get_public_streams',
            dataType: 'json',
            timeout:  10*1000,
            success: function (data) {
                if (data) {
                    all_streams = data.streams;
                    maybe_populate_subscriptions();
                }
            },
            error: function (xhr) {
                util.destroy_loading_indicator($('#subs_page_loading_indicator'));
                ui.report_error("Error listing subscriptions", xhr, $("#subscriptions-status"));
            }
        });
    } else {
        all_streams = [];
        $('#create_stream_button').val("Subscribe");
    }

    $.ajax({
        type:     'POST',
        url:      '/json/subscriptions/list',
        dataType: 'json',
        timeout:  10*1000,
        success: function (data) {
            if (data) {
                our_subs = data.subscriptions;
                maybe_populate_subscriptions();
            }
        },
        error: function (xhr) {
            util.destroy_loading_indicator($('#subs_page_loading_indicator'));
            ui.report_error("Error listing subscriptions", xhr, $("#subscriptions-status"));
        }
    });
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

    $.ajax({
        type: "POST",
        url: "/json/subscriptions/add",
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        data: {"subscriptions": JSON.stringify([stream]) },
        success: function (resp, statusText, xhr, form) {
            $("#create_stream_name").val("");

            var res = $.parseJSON(xhr.responseText);
            if (!$.isEmptyObject(res.already_subscribed)) {
                // Display the canonical stream capitalization.
                true_stream_name = res.already_subscribed[email][0];
                ui.report_success("Already subscribed to " + true_stream_name,
                                  $("#subscriptions-status"));
            } else {
                // Display the canonical stream capitalization.
                true_stream_name = res.subscribed[email][0];
            }
            mark_subscribed(true_stream_name);
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
            if (res.removed.length === 0) {
                name = res.not_subscribed[0];
            } else {
                name = res.removed[0];
            }
            mark_unsubscribed(name);
        },
        error: function (xhr) {
            ui.report_error("Error removing subscription", xhr, $("#subscriptions-status"));
            $("#create_stream_name").focus();
        }
    });
}

function ajaxSubscribeForCreation(stream, principals, invite_only) {
    // Subscribe yourself and possible other people to a new stream.
    $.ajax({
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
            mark_subscribed(stream, {invite_only: invite_only});
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
        ajaxSubscribeForCreation(stream_name, [email], false);
    } else {
        ajaxSubscribe(stream_name);
    }
};

exports.tutorial_unsubscribe_me_from = function (stream_name) {
    ajaxUnsubscribe(stream_name);
};

function people_cmp(person1, person2) {
    // Compares objects of the form used in people_list.
    var name_cmp = person1.full_name.localeCompare(person2.full_name);
    if (name_cmp < 0) {
        return -1;
    } else if (name_cmp > 0) {
        return 1;
    }
    return person1.email.localeCompare(person2.email);
}

function show_new_stream_modal() {
    var people_minus_you_and_maybe_humbuggers = [];
    $.each(people_list, function (idx, person) {
        if (person.email !== email &&
               (domain === "humbughq.com" ||
                   person.email.split('@')[1] !== "humbughq.com"
               )
           ) {
            people_minus_you_and_maybe_humbuggers.push({"email": person.email,
                "full_name": person.full_name});
        }
    });

    $('#people_to_add').html(templates.new_stream_users({
        users: people_minus_you_and_maybe_humbuggers.sort(people_cmp)
    }));
    $('#stream-creation').modal("show");
}

$(function () {
    var i;
    // Populate stream_info with data handed over to client-side template.
    for (i = 0; i < stream_list.length; i++) {
        create_sub(stream_list[i].name, stream_list[i]);
    }

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
        principals.push(email);
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
        var colorpicker = $(e.target).closest('.subscription_row').find('.colorpicker');
        colorpicker.spectrum(colorpicker_options);
    });

    $("#subscriptions_table").on("click", ".sub_setting_show_in_home", stream_home_view_clicked);

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
                    if (principal === email) {
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

exports.set_all_users = function (e, val) {
    $('#people_to_add :checkbox').attr('checked', val);
    e.preventDefault();
};

return exports;

}());
