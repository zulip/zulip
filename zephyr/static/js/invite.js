var invite = (function () {

var exports = {};

function update_subscription_checkboxes() {
    // TODO: If we were more clever, we would only do this if the
    // stream list has actually changed; that way, the settings of the
    // checkboxes are saved from invocation to invocation (which is
    // nice if I want to invite a bunch of people at once)
    var streams = [];
    $.each(subs.subscribed_streams(), function (index, value) {
        streams.push({name: value, invite_only: subs.get_invite_only(value)});
    });
    $('#streams_to_add').html(templates.render('invite_subscription', {streams: streams}));
}

function reset_error_messages() {
    var invite_status = $('#invite_status');
    var invitee_emails = $("#invitee_emails");
    var invitee_emails_group = invitee_emails.closest('.control-group');

    invite_status.hide().text('').removeClass('alert-error alert-warning alert-success');
    invitee_emails_group.removeClass('warning error');
}

function prepare_form_to_be_shown() {
    update_subscription_checkboxes();
    reset_error_messages();
}

exports.initialize = function () {
    var invite_status = $('#invite_status');
    var invitee_emails = $("#invitee_emails");
    var invitee_emails_group = invitee_emails.closest('.control-group');

    $('#submit-invitation').button();
    $('#invite-user').on('show', prepare_form_to_be_shown);
    invitee_emails.focus();
    invitee_emails.autosize();
    $("#invite_user_form").ajaxForm({
        dataType: 'json',
        beforeSubmit: function(arr, $form, options) {
            reset_error_messages();
            // TODO: You could alternatively parse the textarea here, and return errors to
            // the user if they don't match certain constraints (i.e. not real email addresses,
            // aren't in the right domain, etc.)
            //
            // OR, you could just let the server do it. Probably my temptation.
            $('#submit-invitation').button('loading');
            return true;
        },
        success: function (resp, statusText, xhr, form) {
            $('#submit-invitation').button('reset');
            $('#invitee_emails').val('');
            invite_status.text('Users invited successfully.')
                          .addClass('alert-success')
                          .show();
        },
        error: function (xhr, error_type, xhn) {
            $('#submit-invitation').button('reset');
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
