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
        $('#subscriptions_table').prepend(templates.subscription({subscription: stream_name}));
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
            $('#streams').focus().select();
        },
        error: function (xhr) {
            report_error("Error listing subscriptions", xhr, $("#subscriptions-status"));
        }
    });
};

exports.subscribe_for_send = function (stream, prompt_button) {
    $.ajax({
        type:     'POST',
        url:      '/json/subscriptions/add',
        // The next line is a total hack to format our stream as
        // that simplejson will parse as a 1-element array
        data: {"streams": '["' + stream + '"]' },
        dataType: 'json',
        timeout:  10*60*1000, // 10 minutes in ms
        success: function (response) {
            add_to_stream_list(stream);
            compose.finish();
            prompt_button.stop(true).fadeOut(500);
        },
        error: function (xhr, error_type, exn) {
            report_error("Unable to subscribe", xhr, $("#home-error"));
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

    $("#add_new_subscription").on("submit", function (e) {
        e.preventDefault();
        $.ajax({
            type: "POST",
            url: "/json/subscriptions/add",
            dataType: 'json', // This seems to be ignored. We still get back an xhr.
            // The next line is a total hack to format our stream as
            // that simplejson will parse as a 1-element array
            data: {"streams": '["' + $("#streams").val() + '"]' },
            success: function (resp, statusText, xhr, form) {
                $("#streams").val("");
                var name, res = $.parseJSON(xhr.responseText);
                if (res.subscribed.length === 0) {
                    name = res.already_subscribed[0];
                    report_success("Already subscribed to " + name, $("#subscriptions-status"));
                } else {
                    name = res.subscribed[0];
                    report_success("Successfully added subscription to " + name,
                                   $("#subscriptions-status"));
                }
                add_to_stream_list(name);
                $("#streams").focus();
            },
            error: function (xhr) {
                report_error("Error adding subscription", xhr, $("#subscriptions-status"));
                $("#streams").focus();
            }
        });
    });
});

return exports;

}());
