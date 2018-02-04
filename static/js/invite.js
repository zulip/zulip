var invite = (function () {

var exports = {};

var selected_streams;
var multiuse_invites;

function update_subscription_input() {
    // TODO: If we were more clever, we would only do this if the
    // stream list has actually changed; that way, the settings of the
    // checkboxes are saved from invocation to invocation (which is
    // nice if I want to invite a bunch of people at once)
    var all_streams = [];
    var default_streams = [];

    _.each(stream_data.invite_streams(), function (value) {
        var is_notifications_stream = value === page_params.notifications_stream;
        if ((stream_data.subscribed_streams().length === 1) ||
            !is_notifications_stream ||
            (is_notifications_stream && stream_data.get_invite_only(value))) {
            // You can't actually elect not to invite someone to the
            // notifications stream. We won't even show it as a choice unless
            // it's the only stream you have, or if you've made it private.
            if (stream_data.get_default_status(value)) {
                default_streams.push(value);
            }
            if (value !== 'all') {
                all_streams.push(value);
            }
        }
    });
    selected_streams = default_streams.slice();

    var pill_container = $("#edit_streams");
    pill_container.html('<input id="add_invite_stream_input" class="input" placeholder= "Add or edit" />');
    var pills = input_pill(pill_container);

    $("#edit_streams .pill").remove();

    pills.onPillCreate(function (value, reject) {
        if (all_streams.indexOf(value) === -1 || pills.keys().indexOf(value) >= 0) {
            return reject();
        }
        selected_streams.push(value);
        return { key: value, value: '#' + value };
    });

    pills.onPillRemove(function () {
        selected_streams = pills.keys();
    });

    selected_streams.forEach(function (value) {
        pills.pill.append(value);
    });

    var input = $('#add_invite_stream_input');
    input.typeahead({
        items: all_streams.length,
        fixed: true,
        source: all_streams,
        matcher: function (item) {
            if (pills.keys().indexOf(item) >= 0) {
                return false;
            }
            return true;
        },
        updater: function (stream) {
            pills.pill.append(stream);
            input.text('');
        },
        stopAdvance: true,
        menu: '<ul id="scrollable-dropdown-menu" class="typeahead dropdown-menu"></ul>',
    });

    $('#add_invite_stream_input').on('input', function () {
        $(this).attr('size', Math.max(14, $(this).val().length));
    });

}

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

function show_invite_by_email() {
    $('#invite-by-email').show();
    $('#cancel-invitation-button').show();
    $('#submit-invitation-button').show();
    $('#invite-streams').show();
    $('#back-invitation-button').hide();
    $('#create-invitation-link-button').hide();
    $('#multiuse-invite-link-group').hide();
    $('#invite_user_form').attr('action', '/json/invites');
    multiuse_invites = false;
}

function prepare_form_to_be_shown() {
    update_subscription_input();
    reset_error_messages();
    $('#multiuse-invite').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        $('#invite-by-email').hide();
        $('#cancel-invitation-button').hide();
        $('#submit-invitation-button').hide();
        $('#back-invitation-button').show();
        $('#create-invitation-link-button').show();
        $('#invite-streams').show();
        $('#invite_user_form').attr('action', '/json/multiuse_invites');
        multiuse_invites = true;
    });
    $('#back-invitation-button').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        show_invite_by_email();
    });
    show_invite_by_email();
}

exports.initialize = function () {
    ui.set_up_scrollbar($("#invite_user_form .modal-body"));
    var invite_status = $('#invite_status');
    var invitee_emails = $("#invitee_emails");
    var invitee_emails_group = invitee_emails.closest('.control-group');
    var invite_status_timeout = 3000;

    $('#submit-invitation').button();
    prepare_form_to_be_shown();
    invitee_emails.focus().autosize();

    $("#invite_user_form").ajaxForm({
        dataType: 'json',
        beforeSubmit: function (formData) {
            reset_error_messages();
            // TODO: You could alternatively parse the textarea here, and return errors to
            // the user if they don't match certain constraints (i.e. not real email addresses,
            // aren't in the right domain, etc.)
            //
            // OR, you could just let the server do it. Probably my temptation.
            $('#submit-invitation').button('loading');
            selected_streams.forEach(function (stream) {
                formData.push({name: "stream", value: stream});
            });
            return true;
        },
        success: function (data) {
            if (multiuse_invites) {
                $('#create-invitation-link-button').button('reset');
                $('#back-invitation-button').hide();
                $('#invite-streams').hide();
                $('#multiuse-invite-link-group').show();
                $('#multiuse-invite-link').val(data.invite_link);
                $('#create-invitation-link-button').hide();
                $('#copy-link-button').on('click', function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    $('#multiuse-invite-link').select();
                    document.execCommand('copy');
                });
            } else {
                $('#submit-invitation-button').button('reset');
            }
            invite_status.text(i18n.t('User(s) invited successfully.'))
                        .addClass('alert-success')
                        .show();
            invitee_emails.val('');

            if (page_params.development_environment) {
                var email_msg = templates.render('dev_env_email_access');
                $('#dev_env_msg').html(email_msg).addClass('alert-info').show();
            }

            setTimeout(reset_error_messages, invite_status_timeout);

        },
        error: function (xhr) {
            $('#submit-invitation-button').button('reset');
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

            setTimeout(reset_error_messages, invite_status_timeout);

        },
    });

    overlays.open_overlay({
        name: 'invite',
        overlay: $('#invite-user'),
        on_close: function () {
            hashchange.exit_overlay();
        },
    });
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = invite;
}
