var subs = (function () {

var exports = {};

var stream_info = {}; // Maps lowercase stream name to stream properties object
// We fetch the stream colors asynchronous while the message feed is
// getting constructed, so we may need to go back and color streams
// that have already been rendered.
var initial_color_fetch = true;

var default_color = "#c2c2c2";
var next_sub_id = 0;

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

function should_render_subscribers() {
    return domain !== 'mit.edu';
}

function should_list_all_streams() {
    return domain !== 'mit.edu';
}

function update_table_stream_color(table, stream_name, color) {
    $.each(table.find(".stream_label"), function () {
        if ($(this).text() === stream_name) {
            var parent_label = $(this).parent("td");
            parent_label.css("background-color", color);
            parent_label.prev("td").css("background-color", color);
        }
    });
}

function update_historical_message_color(stream_name, color) {
    update_table_stream_color($(".focused_table"), stream_name, color);
    if ($(".focused_table").attr("id") !== "#zhome") {
        update_table_stream_color($("#zhome"), stream_name, color);
    }
}

function update_stream_color(stream_name, color, opts) {
    opts = $.extend({}, {update_historical: false}, opts);
    var sub = stream_info[stream_name.toLowerCase()];
    sub.color = color;
    var id = parseInt(sub.id, 10);
    $("#subscription_" + id + " .color_swatch").css('background-color', color);
    if (opts.update_historical) {
        update_historical_message_color(stream_name, color);
    }
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

        update_stream_color(stream_name, hex_color, {update_historical: true});

        $.ajax({
            type:     'POST',
            url:      '/json/subscriptions/property',
            dataType: 'json',
            data: {
                "property": "stream_colors",
                "stream_name": stream_name,
                "color": hex_color
            },
            timeout:  10*1000
        });
    }
};

function create_sub(stream_name, attrs) {
    var sub = $.extend({}, {name: stream_name, color: default_color, id: next_sub_id++,
                            render_subscribers: should_render_subscribers(),
                            subscribed: true}, attrs);
    stream_info[stream_name.toLowerCase()] = sub;
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

function mark_subscribed(stream_name) {
    var lstream_name = stream_name.toLowerCase();
    var sub = stream_info[lstream_name];

    if (sub === undefined) {
        sub = create_sub(stream_name, {});
        add_sub_to_table(sub);
    } else if (! sub.subscribed) {
        sub.subscribed = true;
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
        sub_row.find(".color_swatch").removeClass("invisible");
        sub_row.find(".regular_subscription_settings").show();
    } else {
        // Already subscribed
        return;
    }
    typeahead_helper.update_autocomplete();
}

function mark_unsubscribed(stream_name) {
    var lstream_name = stream_name.toLowerCase();
    var sub = stream_info[lstream_name];

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
        sub_row.find(".color_swatch").addClass("invisible");
        if (sub.render_subscribers) {
            // TODO: having a completely empty settings div messes
            // with Bootstrap's collapser.  We currently just ensure
            // that it's not empty on the MIT realm, even though it
            // looks weird
            sub_row.find(".regular_subscription_settings").hide();
        }
    } else {
        // Already unsubscribed
        return;
    }
    typeahead_helper.update_autocomplete();
}

exports.get_color = function (stream_name) {
    var lstream_name = stream_name.toLowerCase();
    if (stream_info[lstream_name] === undefined) {
        return default_color;
    }
    return stream_info[lstream_name].color;
};

function fetch_colors() {
    $.ajax({
        type:     'GET',
        url:      '/json/subscriptions/property',
        dataType: 'json',
        data: {"property": "stream_colors"},
        timeout:  10*1000,
        success: function (data) {
            if (data) {
                $.each(data.stream_colors, function (index, data) {
                    var stream_name = data[0];
                    var color = data[1];
                    update_stream_color(stream_name, color,
                                        {update_historical: initial_color_fetch});
                });
                initial_color_fetch = false;
            }
        }
    });
}

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
        our_subs.forEach(function (elem) {
            var stream_name = elem[0];
            var sub = create_sub(stream_name, {color: elem[1], subscribed: true});
            stream_info[stream_name.toLowerCase()] = sub;
            sub_rows.push(sub);
        });

        all_streams.forEach(function (stream) {
            if (exports.have(stream)) {
                return;
            }
            var sub = create_sub(stream, {subscribed: false});
            stream_info[stream.toLowerCase()] = sub;
            sub_rows.push(sub);
        });

        sub_rows.sort(function (a, b) {
            return a.name.localeCompare(b.name);
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

exports.subscribe_for_send = function (stream, prompt_button) {
    $.ajax({
        type:     'POST',
        url:      '/json/subscriptions/add',
        data: {"subscriptions": JSON.stringify([stream]) },
        dataType: 'json',
        timeout:  10*60*1000, // 10 minutes in ms
        success: function (response) {
            mark_subscribed(stream);
            compose.finish();
            if (prompt_button !== undefined)
                prompt_button.stop(true).fadeOut(500);
        },
        error: function (xhr, error_type, exn) {
            ui.report_error("Unable to subscribe", xhr, $("#home-error"));
        }
    });
};

exports.have = function (stream_name) {
    var sub = stream_info[stream_name.toLowerCase()];
    if (sub !== undefined && sub.subscribed) {
        return sub;
    }
    return false;
};

function ajaxSubscribe(stream) {
    $.ajax({
        type: "POST",
        url: "/json/subscriptions/add",
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        data: {"subscriptions": JSON.stringify([stream]) },
        success: function (resp, statusText, xhr, form) {
            if ($("#create_stream_name").val() === stream) {
                $("#create_stream_name").val("");
            }
            var name, res = $.parseJSON(xhr.responseText);
            if (res.subscribed.length === 0) {
                name = res.already_subscribed[0];
                ui.report_success("Already subscribed to " + name, $("#subscriptions-status"));
            } else {
                name = res.subscribed[0];
            }
            mark_subscribed(name);
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
            if (res.removed.length === 0) {
                name = res.not_subscribed[0];
                ui.report_success("Already not subscribed to " + name,
                               $("#subscriptions-status"));
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

$(function () {
    var i;
    // Populate stream_info with data handed over to client-side template.
    for (i = 0; i < stream_list.length; i++) {
        stream_info[stream_list[i].toLowerCase()] = create_sub(stream_list[i]);
    }
    fetch_colors();

    $("#add_new_subscription").on("submit", function (e) {
        e.preventDefault();
        ajaxSubscribe($("#create_stream_name").val());
    });

    $("#subscriptions_table").on("click", ".sub_unsub_button", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var sub_row = $(e.target).closest('.subscription_row');
        var stream_name = sub_row.find('.subscription_name').text();
        var sub = stream_info[stream_name.toLowerCase()];

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
                   "principal": principal},
            success: function (data) {
                text_box.val('');
                if (data.subscribed.length) {
                    error_elem.addClass("hide");
                    warning_elem.addClass("hide");
                    add_to_member_list(list, people_dict[principal].full_name, principal);
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

    $("#subscriptions_table").on("show", ".subscription_settings", function (e) {
        var sub_row = $(e.target).closest('.subscription_row');
        var stream = sub_row.find('.subscription_name').text();
        var error_elem = sub_row.find('.subscriber_list_container .alert-error');
        var list = sub_row.find('.subscriber_list_container ul');
        var indicator_elem = sub_row.find('.subscriber_list_loading_indicator');

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
                $.each(subscribers.sort(), function (idx, elem) {
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

return exports;

}());
