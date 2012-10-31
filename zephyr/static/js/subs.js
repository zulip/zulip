var subs = (function () {

var exports = {};

var stream_list_hash = [];

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

function add_to_stream_list(stream_name) {
    if (!exports.have(stream_name)) {
        stream_list.push(stream_name);
        stream_list_hash[stream_name.toLowerCase()] = true;
    }
}

function remove_from_stream_list(stream_name) {
    delete stream_list_hash[stream_name.toLowerCase()];
    var removal_index = case_insensitive_subscription_index(stream_name);
    if (removal_index !== -1) {
        stream_list.splice(removal_index, 1);
    }
}

exports.fetch = function () {
    $.ajax({
        type:     'POST',
        url:      'json/subscriptions/list',
        dataType: 'json',
        timeout:  10*1000,
        success: function (data) {
            $('#subscriptions_table tr').remove();
            if (data) {
                $.each(data.subscriptions, function (index, name) {
                    $('#subscriptions_table').append(templates.subscription({subscription: name}));
                });
            }
            $('#new_subscription').focus().select();
        },
        error: function (xhr) {
            report_error("Error listing subscriptions", xhr, $("#subscriptions-status"));
        }
    });
};

function add_for_send_success(stream_name, prompt_button) {
    add_to_stream_list(stream_name);
    compose.finish();
    prompt_button.stop(true).fadeOut(500);
}

exports.add_for_send = function (stream, prompt_button) {
    $.ajax({
        type:     'POST',
        url:      '/json/subscriptions/add',
        data:      {new_subscription: stream},
        dataType: 'json',
        timeout:  10*60*1000, // 10 minutes in ms
        success: function (response) {
            add_for_send_success(response.data, prompt_button);
        },
        error: function (xhr, error_type, exn) {
            if ($.parseJSON(xhr.responseText).msg === "Subscription already exists") {
                // If we're already subscribed, the issue here was
                // actually that the client didn't know we were
                // already subscribed -- so just send the message.
                add_for_send_success(stream, prompt_button);
            } else {
                report_error("Unable to subscribe", xhr, $("#home-error"));
            }
        }
    });
};

exports.have = function (stream_name) {
    return (stream_list_hash[stream_name.toLowerCase()] === true);
};

$(function () {
    var i;
    // Populate stream_list_hash with data handed over to client-side template.
    for (i = 0; i < stream_list.length; i++) {
        stream_list_hash[stream_list[i].toLowerCase()] = true;
    }

    // FIXME: It would be nice to move the UI setup into ui.js.

    $("#current_subscriptions").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr, form) {
            var name = $.parseJSON(xhr.responseText).data;
            $('#subscriptions_table').find('button[value="' + name + '"]').parents('tr').remove();
            remove_from_stream_list(name);
            update_autocomplete();
            report_success("Successfully removed subscription to " + name,
                           $("#subscriptions-status"));
        },
        error: function (xhr) {
            report_error("Error removing subscription", xhr, $("#subscriptions-status"));
        }
    });

    $("#add_new_subscription").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr, form) {
            $("#new_subscription").val("");
            var name = $.parseJSON(xhr.responseText).data;
            $('#subscriptions_table').prepend(templates.subscription({subscription: name}));
            add_to_stream_list(name);
            report_success("Successfully added subscription to " + name,
                           $("#subscriptions-status"));
            $("#new_subscription").focus();
        },
        error: function (xhr) {
            report_error("Error adding subscription", xhr, $("#subscriptions-status"));
            $("#new_subscription").focus();
        }
    });
});

return exports;

}());
