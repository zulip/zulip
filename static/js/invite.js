var invite = (function () {

var exports = {};

function reset_error_messages() {
    var invite_status = $('#invite_status');
    var invitee_emails = $("#invitee_emails");
    var invitee_emails_group = invitee_emails.closest('.control-group');

    invite_status.hide().text('').removeClass('alert-error alert-warning alert-success');
    invitee_emails_group.removeClass('warning error');
    if (page_params.development_environment) {
        $('#dev_env_msg').hide().text('').removeClass('alert-error alert-warning alert-success');
    }
}

function submit_invitation_form() {
    var invite_status = $('#invite_status');
    var invitee_emails = $("#invitee_emails");
    var invitee_emails_group = invitee_emails.closest('.control-group');
    var invite_as = 1;  // Default to Member for non-admins
    if (page_params.is_admin) {
        invite_as = parseInt($('#invite_as').val(), 10);
    }
    var data = {
        invitee_emails: $("#invitee_emails").val(),
        invite_as: invite_as,
        csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').attr('value'),
    };
    var streams = [];
    $.each($("#invite-stream-checkboxes input:checked"), function () {
        streams.push($(this).val());
    });
    data.stream = streams;

    channel.post({
        url: "/json/invites",
        data: data,
        traditional: true,
        beforeSubmit: function () {
            reset_error_messages();
            // TODO: You could alternatively parse the textarea here, and return errors to
            // the user if they don't match certain constraints (i.e. not real email addresses,
            // aren't in the right domain, etc.)
            //
            // OR, you could just let the server do it. Probably my temptation.
            $('#submit-invitation').button('loading');
            return true;
        },
        success: function () {
            $('#submit-invitation').button('reset');
            invite_status.text(i18n.t('User(s) invited successfully.'))
                .addClass('alert-success')
                .show();
            invitee_emails.val('');

            if (page_params.development_environment) {
                var rendered_email_msg = templates.render('dev_env_email_access');
                $('#dev_env_msg').html(rendered_email_msg).addClass('alert-info').show();
            }

        },
        error: function (xhr) {
            $('#submit-invitation').button('reset');
            var arr = JSON.parse(xhr.responseText);
            if (arr.errors === undefined) {
                // There was a fatal error, no partial processing occurred.
                invite_status.text(arr.msg)
                    .addClass('alert-error')
                    .show();
            } else {
                // Some users were not invited.
                var invitee_emails_errored = [];
                var error_list = $('<ul>');
                _.each(arr.errors, function (value) {
                    error_list.append($('<li>').text(value.join(': ')));
                    invitee_emails_errored.push(value[0]);
                });

                invite_status.addClass('alert-warning')
                    .empty()
                    .append($('<p>').text(arr.msg))
                    .append(error_list)
                    .show();
                invitee_emails_group.addClass('warning');

                if (arr.sent_invitations) {
                    invitee_emails.val(invitee_emails_errored.join('\n'));
                }

            }

        },
    });
}

// `get_invite_streams` is further modification of stream_data.invite_streams(), it is
// defined here to keep stream_data.invite_stream() generic.
exports.get_invite_streams = function () {
    var streams = [];

    _.each(stream_data.invite_streams(), function (value) {
        var is_invite_only = stream_data.get_invite_only(value);
        var is_notifications_stream = value === page_params.notifications_stream;

        // You can't actually elect to invite someone to the
        // notifications stream. We won't even show it as a choice unless
        // it's the only stream you have, or if you've made it private.
        if (stream_data.subscribed_streams().length === 1 ||
            !is_notifications_stream ||
            is_notifications_stream && is_invite_only) {

            streams.push({
                name: value,
                invite_only: is_invite_only,
                default_stream: stream_data.get_default_status(value),
            });

            // Sort by default status.
            streams.sort(function (a, b) {
                return b.default_stream - a.default_stream;
            });
        }
    });

    return streams;
};

function update_subscription_checkboxes() {
    var data = {streams: exports.get_invite_streams()};
    var html = templates.render('invite_subscription', data);
    $('#streams_to_add').html(html);
}

function prepare_form_to_be_shown() {
    update_subscription_checkboxes();
    reset_error_messages();
}

exports.launch = function () {
    ui.set_up_scrollbar($("#invite_user_form .modal-body"));

    $('#submit-invitation').button();
    prepare_form_to_be_shown();
    $("#invitee_emails").focus().autosize();

    overlays.open_overlay({
        name: 'invite',
        overlay: $('#invite-user'),
        on_close: function () {
            hashchange.exit_overlay();
        },
    });
};

exports.initialize = function () {
    $(document).on('click', '.invite_check_all_button', function (e) {
        $('#streams_to_add :checkbox').prop('checked', true);
        e.preventDefault();
    });

    $(document).on('click', '.invite_uncheck_all_button', function (e) {
        $('#streams_to_add :checkbox').prop('checked', false);
        e.preventDefault();
    });
    $("#submit-invitation").on("click", submit_invitation_form);
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = invite;
}
window.invite = invite;
