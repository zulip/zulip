var invite = (function () {

var exports = {};

function update_subscription_checkboxes() {
    // TODO: If we were more clever, we would only do this if the
    // stream list has actually changed; that way, the settings of the
    // checkboxes are saved from invocation to invocation (which is
    // nice if I want to invite a bunch of people at once)
    $('#streams_to_add').html(templates.invite_subscription({subscriptions: stream_list}));
}

exports.initialize = function () {
    var invite_status = $('#invite_status');
    var invitee_emails = $("#invitee_emails");
    var invitee_emails_group = invitee_emails.closest('.control-group');

    $('#invite-user').on('show', update_subscription_checkboxes);
    invitee_emails.focus();
    invitee_emails.autosize();
    $("#invite_user_form").ajaxForm({
        dataType: 'json',
        clearForm: true,
        beforeSubmit: function(arr, $form, options) {
            invite_status.hide()
                         .removeClass('alert-error alert-warning alert-success');
            invitee_emails_group.removeClass('warning error');
            // The array of form data takes the following form:
            // [ { name: 'username', value: 'jresig' }, { name: 'password', value: 'secret' } ]
            // TODO: You could alternatively parse the textarea here, and return errors to
            // the user if they don't match certain constraints (i.e. not real email addresses,
            // aren't in the right domain, etc.)
            //
            // OR, you could just let the server do it. Probably my temptation.
            return true;
        },
        success: function (resp, statusText, xhr, form) {
            invite_status.text('Users invited successfully.')
                          .addClass('alert-success')
                          .show();
        },
        error: function (xhr, error_type, xhn) {
            var arr = $.parseJSON(xhr.responseText);
            if (arr.errors === undefined) {
                // There was a fatal error, no partial processing occurred.
                invite_status.text(arr.msg)
                              .addClass('alert-error')
                              .show();
            } else {
                // Some users were not invited.
                var error_list = $('<ul>');
                $.each(arr.errors, function (index, value) {
                    error_list.append($('<li>').text(value.join(': ')));
                });

                invite_status.addClass('alert-warning')
                              .empty()
                              .append($('<p>').text(arr.msg))
                              .append(error_list)
                              .show();
                invitee_emails_group.addClass('warning');

            }

        }
    });
};

exports.set_all_streams = function (e, val) {
    $('#streams_to_add :checkbox').attr('checked', val);
    e.preventDefault();
};

return exports;

}());
