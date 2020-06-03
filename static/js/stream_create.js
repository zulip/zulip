const render_announce_stream_docs = require('../templates/announce_stream_docs.hbs');
const render_new_stream_users = require('../templates/new_stream_users.hbs');
const render_subscription_invites_warning_modal = require('../templates/subscription_invites_warning_modal.hbs');

let created_stream;

exports.reset_created_stream = function () {
    created_stream = undefined;
};

exports.set_name = function (stream) {
    created_stream = stream;
};

exports.get_name = function () {
    return created_stream;
};

const stream_subscription_error = (function () {
    const self = {};

    self.report_no_subs_to_stream = function () {
        $("#stream_subscription_error").text(i18n.t("You cannot create a stream with no subscribers!"));
        $("#stream_subscription_error").show();
    };

    self.cant_create_stream_without_susbscribing = function () {
        $("#stream_subscription_error").text(i18n.t("You must be an organization administrator to create a stream without subscribing."));
        $("#stream_subscription_error").show();
    };

    self.clear_errors = function () {
        $("#stream_subscription_error").hide();
    };

    return self;

}());

const stream_name_error = (function () {
    const self = {};

    self.report_already_exists = function () {
        $("#stream_name_error").text(i18n.t("A stream with this name already exists"));
        $("#stream_name_error").show();
    };

    self.clear_errors = function () {
        $("#stream_name_error").hide();
    };

    self.report_empty_stream = function () {
        $("#stream_name_error").text(i18n.t("A stream needs to have a name"));
        $("#stream_name_error").show();
    };

    self.select = function () {
        $("#create_stream_name").focus().select();
    };

    self.pre_validate = function (stream_name) {
        // Don't worry about empty strings...we just want to call this
        // to warn users early before they start doing too much work
        // after they make the effort to type in a stream name.  (The
        // use case here is that I go to create a stream, only to find
        // out it already exists, and I was just too lazy to look at
        // the public streams that I'm not subscribed to yet.  Once I
        // realize the stream already exists, I may want to cancel.)
        if (stream_name && stream_data.get_sub(stream_name)) {
            self.report_already_exists();
            return;
        }

        self.clear_errors();
    };

    self.validate_for_submit = function (stream_name) {
        if (!stream_name) {
            self.report_empty_stream();
            self.select();
            return false;
        }

        if (stream_data.get_sub(stream_name)) {
            self.report_already_exists();
            self.select();
            return false;
        }

        // If we got this far, then we think we have a new unique stream
        // name, so we'll submit to the server.  (It's still plausible,
        // however, that there's some invite-only stream that we don't
        // know about locally that will cause a name collision.)
        return true;
    };

    return self;
}());

// Within the new stream modal...
function update_announce_stream_state() {

    // If there is no notifications_stream, we simply hide the widget.
    if (!stream_data.realm_has_notifications_stream()) {
        $('#announce-new-stream').hide();
        return;
    }

    // If the stream is invite only, disable the "Announce stream" option.
    // Otherwise enable it.
    const announce_stream_checkbox = $('#announce-new-stream input');
    const announce_stream_label = $('#announce-new-stream');
    let disable_it = false;
    const privacy_type = $('input:radio[name=privacy]:checked').val();
    const is_invite_only = privacy_type === "invite-only" || privacy_type === "invite-only-public-history";
    announce_stream_label.removeClass("control-label-disabled");

    if (is_invite_only) {
        disable_it = true;
        announce_stream_checkbox.prop('checked', false);
        announce_stream_label.addClass("control-label-disabled");
    }

    announce_stream_checkbox.prop('disabled', disable_it);
    $('#announce-new-stream').show();
}

function get_principals() {
    return Array.from($("#stream_creation_form input:checkbox[name=user]:checked"), elem => {
        const label = $(elem).closest(".add-user-label");
        return parseInt(label.attr("data-user-id"), 10);
    });
}

function create_stream() {
    const data = {};
    const stream_name = $.trim($("#create_stream_name").val());
    const description = $.trim($("#create_stream_description").val());
    created_stream = stream_name;

    // Even though we already check to make sure that while typing the user cannot enter
    // newline characters (by pressing the enter key) it would still be possible to copy
    // and paste over a description with newline characters in it. Prevent that.
    if (description.includes('\n')) {
        ui_report.message(i18n.t("The stream description cannot contain newline characters."),
                          $(".stream_create_info"), 'alert-error');
        return;
    }
    data.subscriptions = JSON.stringify([{name: stream_name, description: description}]);

    let invite_only;
    let history_public_to_subscribers;
    const privacy_setting = $('#stream_creation_form input[name=privacy]:checked').val();

    if (privacy_setting === 'invite-only') {
        invite_only = true;
        history_public_to_subscribers = false;
    } else if (privacy_setting === 'invite-only-public-history') {
        invite_only = true;
        history_public_to_subscribers = true;
    } else {
        invite_only = false;
        history_public_to_subscribers = true;
    }
    data.invite_only = JSON.stringify(invite_only);
    data.history_public_to_subscribers = JSON.stringify(history_public_to_subscribers);

    const stream_post_policy = parseInt($('#stream_creation_form input[name=stream-post-policy]:checked').val(), 10);

    data.stream_post_policy = JSON.stringify(stream_post_policy);

    const announce = stream_data.realm_has_notifications_stream() &&
        $('#announce-new-stream input').prop('checked');
    data.announce = JSON.stringify(announce);

    // TODO: We can eliminate the user_ids -> principals conversion
    //       once we upgrade the backend to accept user_ids.
    const user_ids = get_principals();
    data.principals = JSON.stringify(user_ids);

    loading.make_indicator($('#stream_creating_indicator'), {text: i18n.t('Creating stream...')});

    // Subscribe yourself and possible other people to a new stream.
    return channel.post({
        url: "/json/users/me/subscriptions",
        data: data,
        success: function () {
            $("#create_stream_name").val("");
            $("#create_stream_description").val("");
            ui_report.success(i18n.t("Stream successfully created!"), $(".stream_create_info"));
            loading.destroy_indicator($('#stream_creating_indicator'));
            // The rest of the work is done via the subscribe event we will get
        },
        error: function (xhr) {
            const msg = JSON.parse(xhr.responseText).msg;
            if (msg.includes('access')) {
                // If we can't access the stream, we can safely assume it's
                // a duplicate stream that we are not invited to.
                //
                // BUG: This check should be using error codes, not
                // parsing the error string, so it works correctly
                // with i18n.  And likely we should be reporting the
                // error text directly rather than turning it into
                // "Error creating stream"?
                stream_name_error.report_already_exists(stream_name);
                stream_name_error.select();
            }

            ui_report.error(i18n.t("Error creating stream"), xhr, $(".stream_create_info"));
            loading.destroy_indicator($('#stream_creating_indicator'));
        },
    });
}

exports.new_stream_clicked = function (stream_name) {
    // this changes the tab switcher (settings/preview) which isn't necessary
    // to a add new stream title.
    $(".display-type #add_new_stream_title").show();
    $(".display-type #stream_settings_title").hide();

    $(".stream-row.active").removeClass("active");

    $("#stream_settings_title, .subscriptions-container .settings, .nothing-selected").hide();
    $("#stream-creation, #add_new_stream_title").show();

    if (stream_name !== '') {
        $('#create_stream_name').val(stream_name);
    }
    exports.show_new_stream_modal();

    // at less than 700px we have a @media query that when you tap the
    // .create_stream_button, the stream prompt slides in. However, when you
    // focus  the button on that page, the entire app view jumps over to
    // the other tab, and the animation breaks.
    // it is unclear whether this is a browser bug or "feature", however what
    // is clear is that this shouldn't be touched unless you're also changing
    // the mobile @media query at 700px.
    if (window.innerWidth > 700) {
        $('#create_stream_name').focus();
    }
};

function clear_error_display() {
    stream_name_error.clear_errors();
    $(".stream_create_info").hide();
    stream_subscription_error.clear_errors();
}

exports.show_new_stream_modal = function () {
    $("#stream-creation").removeClass("hide");
    $(".right .settings").hide();

    const all_users = people.get_people_for_stream_create();
    // Add current user on top of list
    all_users.unshift(people.get_by_user_id(page_params.user_id));
    const html = render_new_stream_users({
        users: all_users,
        streams: stream_data.get_streams_for_settings_page(),
        is_admin: page_params.is_admin,
    });

    const container = $('#people_to_add');
    container.html(html);
    exports.create_handlers_for_users(container);

    // Make the options default to the same each time:
    // public, "announce stream" on.
    $('#make-invite-only input:radio[value=public]').prop('checked', true);

    if (stream_data.realm_has_notifications_stream()) {
        $('#announce-new-stream').show();
        $('#announce-new-stream input').prop('disabled', false);
        $('#announce-new-stream input').prop('checked', true);
    } else {
        $('#announce-new-stream').hide();
    }
    clear_error_display();

    $("#stream-checkboxes label.checkbox").on('change', function (e) {
        const elem = $(this);
        const stream_id = parseInt(elem.attr('data-stream-id'), 10);
        const checked = elem.find('input').prop('checked');
        const subscriber_ids = stream_data.get_sub_by_id(stream_id).subscribers;

        $('#user-checkboxes label.checkbox').each(function () {
            const user_elem = $(this);
            const user_id = parseInt(user_elem.attr('data-user-id'), 10);

            if (subscriber_ids.has(user_id)) {
                user_elem.find('input').prop('checked', checked);
            }
        });

        e.preventDefault();
    });
};

exports.create_handlers_for_users = function (container) {
    // container should be $('#people_to_add')...see caller to verify
    container.on('change', '#user-checkboxes input', update_announce_stream_state);

    // 'Check all' and 'Uncheck all' visible users
    container.on('click', '.subs_set_all_users', function (e) {
        $('#user-checkboxes .checkbox').each(function (idx, li) {
            if  (li.style.display !== "none") {
                $(li.firstElementChild).prop('checked', true);
            }
        });
        e.preventDefault();
        update_announce_stream_state();
    });

    container.on('click', '.subs_unset_all_users', function (e) {
        $('#user-checkboxes .checkbox').each(function (idx, li) {
            if (li.style.display !== "none") {
                // The first checkbox is the one for ourself; this is the code path for:
                // `stream_subscription_error.cant_create_stream_without_susbscribing`
                if (idx === 0 && !page_params.is_admin) {
                    return;
                }
                $(li.firstElementChild).prop('checked', false);
            }
        });
        e.preventDefault();
        update_announce_stream_state();
    });

    container.on('click', '#copy-from-stream-expand-collapse', function (e) {
        $('#stream-checkboxes').toggle();
        $("#copy-from-stream-expand-collapse .toggle").toggleClass('fa-caret-right fa-caret-down');
        e.preventDefault();
    });

    // Search People or Streams
    container.on('input', '.add-user-list-filter', function (e) {
        const user_list = $(".add-user-list-filter");
        if (user_list === 0) {
            return;
        }
        const search_term = user_list.expectOne().val().trim();
        const search_terms = search_term.toLowerCase().split(",");

        (function filter_user_checkboxes() {
            const user_labels = $("#user-checkboxes label.add-user-label");

            if (search_term === '') {
                user_labels.css({display: 'block'});
                return;
            }

            const users = people.get_people_for_stream_create();
            const filtered_users = people.filter_people_by_search_terms(users, search_terms);

            // Be careful about modifying the follow code.  A naive implementation
            // will work very poorly with a large user population (~1000 users).
            //
            // I tested using: `./manage.py populate_db --extra-users 3500`
            //
            // This would break the previous implementation, whereas the new
            // implementation is merely sluggish.
            user_labels.each(function () {
                const elem = $(this);
                const user_id = parseInt(elem.attr('data-user-id'), 10);
                const user_checked = filtered_users.has(user_id);
                const display = user_checked ? "block" : "none";
                elem.css({display: display});
            });
        }());

        e.preventDefault();
    });
};


exports.set_up_handlers = function () {
    const container = $('#stream-creation').expectOne();

    container.on('change', '#make-invite-only input', update_announce_stream_state);

    container.on("submit", "#stream_creation_form", function (e) {
        e.preventDefault();
        clear_error_display();

        const stream_name = $.trim($("#create_stream_name").val());
        const name_ok = stream_name_error.validate_for_submit(stream_name);

        if (!name_ok) {
            return;
        }

        const principals = get_principals();
        if (principals.length === 0) {
            stream_subscription_error.report_no_subs_to_stream();
            return;
        }
        if (!principals.includes(people.my_current_user_id()) && !page_params.is_admin) {
            stream_subscription_error.cant_create_stream_without_susbscribing();
            return;
        }

        if (principals.length >= 50) {
            const invites_warning_modal = render_subscription_invites_warning_modal({
                stream_name: stream_name,
                count: principals.length,
            });
            $('#stream-creation').append(invites_warning_modal);
        } else {
            create_stream();
        }
    });

    container.on("click", ".close-invites-warning-modal", function () {
        $("#invites-warning-overlay").remove();
    });

    container.on("click", ".confirm-invites-warning-modal", function () {
        create_stream();
        $("#invites-warning-overlay").remove();
    });

    container.on("input", "#create_stream_name", function () {
        const stream_name = $.trim($("#create_stream_name").val());

        // This is an inexpensive check.
        stream_name_error.pre_validate(stream_name);
    });

    container.on("mouseover", "#announce-stream-docs", function (e) {
        const announce_stream_docs = $("#announce-stream-docs");
        announce_stream_docs.popover({
            placement: "right",
            content: render_announce_stream_docs({
                notifications_stream: stream_data.get_notifications_stream(),
            }),
            html: true,
            trigger: "manual"});
        announce_stream_docs.popover('show');
        announce_stream_docs.data('popover').tip().css('z-index', 2000);
        announce_stream_docs.data('popover').tip().find('.popover-content').css('margin', '9px 14px');
        e.stopPropagation();
    });
    container.on("mouseout", "#announce-stream-docs", function (e) {
        $("#announce-stream-docs").popover('hide');
        e.stopPropagation();
    });

    // Do not allow the user to enter newline characters while typing out the
    // stream's description during it's creation.
    container.on("keydown", "#create_stream_description", function (e) {
        if ((e.keyCode || e.which) === 13) {
            e.preventDefault();
        }
    });

};

window.stream_create = exports;
