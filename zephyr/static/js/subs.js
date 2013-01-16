var subs = (function () {

var exports = {};

var stream_info = {}; // Maps lowercase stream name to stream properties object
var removed_streams = {};
// We fetch the stream colors asynchronous while the message feed is
// getting constructed, so we may need to go back and color streams
// that have already been rendered.
var initial_color_fetch = true;

var default_color = "#c2c2c2";
var next_sub_id = 0;

function render_subscribers() {
    return domain !== 'mit.edu';
}

function case_insensitive_subscription_index(stream_name) {
    var i;
    var name = stream_name.toLowerCase();

    for (i = 1; i < stream_list.length; i++) {
        if (name === stream_list[i].toLowerCase()) {
            return i;
        }
    }
    return -1;
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
        stream_info[stream_name.toLowerCase()].color = hex_color;
        sub_row.find('.color_swatch').css('background-color', hex_color);
        update_historical_message_color(stream_name, hex_color);

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

function add_to_stream_list(stream_name) {
    var stream_sub_row;
    var sub;

    if (exports.have(stream_name)) {
        return;
    }

    var lstream_name = stream_name.toLowerCase();

    stream_list.push(stream_name);

    if (removed_streams[lstream_name] !== undefined) {
        sub = removed_streams[lstream_name];
        delete removed_streams[lstream_name];
        stream_info[lstream_name] = sub;
    } else {
        sub = {name: stream_name, id: next_sub_id++, color: default_color,
               render_subscribers: render_subscribers()};
        stream_info[lstream_name] = sub;

        $('#subscriptions_table').prepend(templates.subscription({subscriptions: [sub]}));
    }
}

function remove_from_stream_list(stream_name) {
    var lstream_name = stream_name.toLowerCase();
    removed_streams[lstream_name] = stream_info[lstream_name];
    delete stream_info[lstream_name];
    var removal_index = case_insensitive_subscription_index(stream_name);
    if (removal_index !== -1) {
        stream_list.splice(removal_index, 1);
    }
}

exports.get_color = function (stream_name) {
    var lstream_name = stream_name.toLowerCase();
    if (stream_info[lstream_name] === undefined) {
        return default_color;
    }
    return stream_info[lstream_name].color;
};

exports.fetch_colors = function () {
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
                    stream_info[stream_name.toLowerCase()].color = color;
                    if (initial_color_fetch) {
                        update_historical_message_color(stream_name, color);
                    }
                });
                initial_color_fetch = false;
            }
        }
    });
};

exports.setup_page = function () {
    // TODO: We really want to show a spinner while we're fetching
    // the subs
    $.ajax({
        type:     'POST',
        url:      '/json/subscriptions/list',
        dataType: 'json',
        timeout:  10*1000,
        success: function (data) {
            $('#subscriptions_table tr').remove();
            removed_streams = {};
            if (data) {
                var subscriptions = [];
                $.each(data.subscriptions, function (index, data) {
                    var stream_name = data[0];
                    var sub = {name: stream_name, id: next_sub_id++,
                               color: data[1], render_subscribers: render_subscribers()};
                    stream_info[stream_name.toLowerCase()] = sub;
                    subscriptions.push(sub);
                });
                $('#subscriptions_table').append(templates.subscription({subscriptions: subscriptions}));
            }
            $('#streams').focus().select();
        },
        error: function (xhr) {
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
            add_to_stream_list(stream);
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
    return (stream_info[stream_name.toLowerCase()] !== undefined);
};

function ajaxSubscribe(stream, button) {
    $.ajax({
        type: "POST",
        url: "/json/subscriptions/add",
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        data: {"subscriptions": JSON.stringify([stream]) },
        success: function (resp, statusText, xhr, form) {
            if ($("#streams").val() === stream) {
                $("#streams").val("");
            }
            var name, res = $.parseJSON(xhr.responseText);
            if (res.subscribed.length === 0) {
                name = res.already_subscribed[0];
                ui.report_success("Already subscribed to " + name, $("#subscriptions-status"));
            } else {
                name = res.subscribed[0];
                ui.report_success("Successfully added subscription to " + name,
                               $("#subscriptions-status"));
            }
            add_to_stream_list(name);
            if (button !== undefined) {
                button.text("Unsubscribe").removeClass("btn-primary");
            }
            typeahead_helper.update_autocomplete();
        },
        error: function (xhr) {
            ui.report_error("Error adding subscription", xhr, $("#subscriptions-status"));
            $("#streams").focus();
        }
    });
}

function ajaxUnsubscribe(stream, button) {
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
                ui.report_success("Successfully removed subscription to " + name,
                               $("#subscriptions-status"));
            }
            remove_from_stream_list(name);
            button.text("Subscribe").addClass("btn-primary");
            typeahead_helper.update_autocomplete();
        },
        error: function (xhr) {
            ui.report_error("Error removing subscription", xhr, $("#subscriptions-status"));
            $("#streams").focus();
        }
    });
}

$(function () {
    var i;
    // Populate stream_info with data handed over to client-side template.
    for (i = 0; i < stream_list.length; i++) {
        stream_info[stream_list[i].toLowerCase()] = {color: default_color};
    }

    $("#add_new_subscription").on("submit", function (e) {
        e.preventDefault();
        ajaxSubscribe($("#streams").val());
    });

    if (! render_subscribers()) {
        return;
    }

    $("#subscriptions_table").on("click", ".sub_unsub_button", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var sub_row = $(e.target).closest('.subscription_row');
        var stream_name = sub_row.find('.subscription_name').text();
        var sub = stream_info[stream_name.toLowerCase()];

        if (sub) {
            ajaxUnsubscribe(stream_name, $(e.target));
        } else {
            ajaxSubscribe(stream_name, $(e.target));
        }
    });

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
                    var subscriber = people_dict[principal].full_name + ' <' + principal + '>';
                    $('<li>').prependTo(list).text(subscriber);
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
        var colorpicker = sub_row.find('.colorpicker');
        colorpicker.spectrum(colorpicker_options);

        error_elem.addClass('hide');
        list.empty();

        // TODO: Show a spinner while the list is loading
        $.ajax({
            type: "POST",
            url: "/json/get_subscribers",
            dataType: 'json', // This seems to be ignored. We still get back an xhr.
            data: {stream: stream},
            success: function (data) {
                var subscribers = $.map(data.subscribers, function (elem) {
                    var person = people_dict[elem];
                    if (person === undefined) {
                        return elem;
                    }
                    return people_dict[elem].full_name + ' <' + elem + '>';
                });
                $.each(subscribers.sort(), function (idx, elem) {
                    $('<li>').appendTo(list).text(elem);
                });
            },
            error: function (xhr) {
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
