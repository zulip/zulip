function fetch_subs() {
    $.ajax({
        type:     'GET',
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
}

function sub_from_home(zephyr_class, prompt_button) {
    $.ajax({
        type:     'POST',
        url:      '/json/subscriptions/add',
        data:      {new_subscription: zephyr_class},
        dataType: 'json',
        timeout:  10*60*1000, // 10 minutes in ms
        success: function (data) {
            $("#zephyr_compose form").ajaxSubmit();
            prompt_button.stop(true).fadeOut(500);
        },
        error: function (xhr, error_type, exn) {
            report_error("Unable to subscribe", xhr, $("#home-error"));
        }
    });
}

// FIXME: It would be nice to move the UI setup into ui.js.
$(function () {
    $("#current_subscriptions").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr, form) {
            var name = $.parseJSON(xhr.responseText).data;
            $('#subscriptions_table').find('button[value="' + name + '"]').parents('tr').remove();
            var removal_index = class_list.indexOf(name.toLowerCase());
            if (removal_index !== -1) {
                class_list.splice(removal_index, 1);
            }
            update_autocomplete();
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
            class_list.push(name.toLowerCase());
            $("#new_subscription").focus();
        },
        error: function (xhr) {
            report_error("Error adding subscription", xhr, $("#subscriptions-status"));
            $("#new_subscription").focus();
        }
    });
});
