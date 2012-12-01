var subs = (function () {

var exports = {};

var stream_set = {};
var stream_colors = {};
// We fetch the stream colors asynchronous while the message feed is
// getting constructed, so we may need to go back and color streams
// that have already been rendered.
var initial_color_fetch = true;

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

// TODO: The way that we find the row is kind of fragile
// and liable to break with streams with " in their name,
// just like our unsubscribe button code.
function draw_colorpicker(stream_name) {
    var colorpicker = $('#subscriptions_table').find('button[value="' + stream_name + '"]')
                                               .parent().prev().find('input');
    colorpicker.spectrum({
        clickoutFiresChange: true,
        showPalette: true,
        palette: [
            ['a47462', 'c2726a', 'e4523d', 'e7664d', 'ee7e4a', 'f4ae55'],
            ['76ce90', '53a063', '94c849', 'bfd56f', 'fae589', 'f5ce6e'],
            ['a6dcbf', 'addfe5', 'a6c7e5', '4f8de4', '95a5fd', 'b0a5fd'],
            ['c2c2c2', 'c8bebf', 'c6a8ad', 'e79ab5', 'bd86e5', '9987e1']
        ],
        change: function (color) {
            var hex_color = color.toHexString();
            stream_colors[stream_name] = hex_color;
            update_historical_message_color(stream_name, hex_color);

            $.ajax({
                type:     'POST',
                url:      '/json/subscriptions/colorize',
                dataType: 'json',
                data: {
                    "stream_name": stream_name,
                    "color": hex_color
                },
                timeout:  10*1000
            });
        }
    });
}

function add_to_stream_list(stream_name) {
    var stream_sub_row;

    if (!exports.have(stream_name)) {
        stream_list.push(stream_name);
        stream_set[stream_name.toLowerCase()] = true;

        stream_sub_row = $('#subscriptions_table').find('button[value="' + stream_name + '"]');
        if (stream_sub_row.length) {
            stream_sub_row.text("Unsubscribe")
                .removeClass("btn-primary")
                .unbind("click")
                .removeAttr("onclick")
                .click(function (event) {exports.unsubscribe(stream_name);});
        } else {
            $('#subscriptions_table').prepend(templates.subscription({
                subscription: stream_name,color: "c2c2c2"}));
            draw_colorpicker(stream_name);
        }
    }
}

function remove_from_stream_list(stream_name) {
    delete stream_set[stream_name.toLowerCase()];
    var removal_index = case_insensitive_subscription_index(stream_name);
    if (removal_index !== -1) {
        stream_list.splice(removal_index, 1);
    }
}

exports.get_color = function (stream_name) {
    return stream_colors[stream_name];
};

exports.fetch_colors = function () {
    $.ajax({
        type:     'POST',
        url:      '/json/subscriptions/colors',
        dataType: 'json',
        timeout:  10*1000,
        success: function (data) {
            if (data) {
                $.each(data.stream_colors, function (index, data) {
                    var stream_name = data[0];
                    var color = data[1];
                    stream_colors[stream_name] = color;
                    if (initial_color_fetch) {
                        update_historical_message_color(stream_name, color);
                    }
                });
                initial_color_fetch = false;
            }
        }
    });
};

exports.fetch = function () {
    $.ajax({
        type:     'POST',
        url:      '/json/subscriptions/list',
        dataType: 'json',
        timeout:  10*1000,
        success: function (data) {
            $('#subscriptions_table tr').remove();
            if (data) {
                $.each(data.subscriptions, function (index, data) {
                    var stream_name = data[0];
                    var color = data[1];
                    stream_colors[stream_name] = color;
                    $('#subscriptions_table').append(templates.subscription({
                        subscription: stream_name, color: color}));
                    draw_colorpicker(stream_name);
                });
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
            prompt_button.stop(true).fadeOut(500);
        },
        error: function (xhr, error_type, exn) {
            ui.report_error("Unable to subscribe", xhr, $("#home-error"));
        }
    });
};

exports.have = function (stream_name) {
    return (stream_set[stream_name.toLowerCase()] === true);
};

function ajaxSubscribe(stream) {
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
            $("#streams").focus();
        },
        error: function (xhr) {
            ui.report_error("Error adding subscription", xhr, $("#subscriptions-status"));
            $("#streams").focus();
        }
    });
}

exports.unsubscribe = function (stream) {
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
            $('#subscriptions_table').find('button[value="' + name + '"]').text("Subscribe")
                .addClass("btn-primary")
                .unbind("click")
                .removeAttr("onclick")
                .click(function (e) {
                    e.preventDefault();
                    ajaxSubscribe(name);
                });
            remove_from_stream_list(name);
            typeahead_helper.update_autocomplete();
            $("#streams").focus();
        },
        error: function (xhr) {
            ui.report_error("Error removing subscription", xhr, $("#subscriptions-status"));
            $("#streams").focus();
        }
    });
};

$(function () {
    var i;
    // Populate stream_set with data handed over to client-side template.
    for (i = 0; i < stream_list.length; i++) {
        stream_set[stream_list[i].toLowerCase()] = true;
    }

    $("#add_new_subscription").on("submit", function (e) {
        e.preventDefault();
        ajaxSubscribe($("#streams").val());
    });
});

return exports;

}());
