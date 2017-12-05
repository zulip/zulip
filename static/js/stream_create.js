var stream_create = (function () {

var exports = {};

var created_stream;

exports.reset_created_stream = function () {
    created_stream = undefined;
};

exports.set_name = function (stream) {
    created_stream = stream;
};

exports.get_name = function () {
    return created_stream;
};

var stream_name_error = (function () {
    var self = {};

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

function ajaxSubscribeForCreation(stream_name, description, principals, invite_only, announce) {
    // Subscribe yourself and possible other people to a new stream.
    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([{name: stream_name,
                                               description: description}]),
               principals: JSON.stringify(principals),
               invite_only: JSON.stringify(invite_only),
               announce: JSON.stringify(announce),
        },
        success: function () {
            $("#create_stream_name").val("");
            $("#create_stream_description").val("");
            $("#subscriptions-status").hide();
            loading.destroy_indicator($('#stream_creating_indicator'));
            // The rest of the work is done via the subscribe event we will get
        },
        error: function (xhr) {
            var msg = JSON.parse(xhr.responseText).msg;
            if (msg.indexOf('access') >= 0) {
                // If we can't access the stream, we can safely assume it's
                // a duplicate stream that we are not invited to.
                stream_name_error.report_already_exists(stream_name);
                stream_name_error.select();
            }

            // TODO: This next line does nothing.  See #4647.
            ui_report.error(i18n.t("Error creating stream"), xhr,
                            $("#subscriptions-status"), 'subscriptions-status');
            loading.destroy_indicator($('#stream_creating_indicator'));
        },
    });
}

// Within the new stream modal...
function update_announce_stream_state() {

    // If there is no notifications_stream, we simply hide the widget.
    if (!page_params.notifications_stream) {
        $('#announce-new-stream').hide();
        return;
    }

    // If the stream is invite only, or everyone's added, disable
    // the "Announce stream" option. Otherwise enable it.
    var announce_stream_checkbox = $('#announce-new-stream input');
    var disable_it = false;
    var is_invite_only = $('input:radio[name=privacy]:checked').val() === 'invite-only';

    if (is_invite_only) {
        disable_it = true;
        announce_stream_checkbox.prop('checked', false);
    } else {
        disable_it = $('#user-checkboxes input').length
                    === $('#user-checkboxes input:checked').length;
    }

    announce_stream_checkbox.prop('disabled', disable_it);
    $('#announce-new-stream').show();
}

function get_principals() {
    var realm_people = exports.show_new_stream_modal.modified_user_list();

    return realm_people
        .filter(function (user) {
            return user.__meta.checked;
        }).map(function (user) {
            return user.email;
        });
}

function create_stream() {
    var stream_name = $.trim($("#create_stream_name").val());
    var description = $.trim($("#create_stream_description").val());
    var is_invite_only = $('#stream_creation_form input[name=privacy]:checked').val() === "invite-only";
    var principals = get_principals();

    // You are always subscribed to streams you create.
    principals.push(people.my_current_email());

    created_stream = stream_name;

    var announce = (!!page_params.notifications_stream &&
        $('#announce-new-stream input').prop('checked'));

    loading.make_indicator($('#stream_creating_indicator'), {text: i18n.t('Creating stream...')});

    ajaxSubscribeForCreation(stream_name,
        description,
        principals,
        is_invite_only,
        announce
    );
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
    // is clear is that this shoudn't be touched unless you're also changing
    // the mobile @media query at 700px.
    if (window.innerWidth > 700) {
        $('#create_stream_name').focus();
    }

    // change the hash to #streams/new to allow for linking and
    // easy discovery.

    window.location.hash = "#streams/new";
};

(function () {
    // only once instance of the stream creation modal can really exist at
    // once so it's okay to have this general instance here at the top.
    var meta = {
        user_list: null,
    };

    exports.show_new_stream_modal = function () {
        $("#stream-creation").removeClass("hide");
        $(".right .settings").hide();

        $('#people_to_add').html(templates.render('new_stream_users', {
            streams: stream_data.get_streams_for_settings_page(),
        }));

        meta.user_list = people.get_rest_of_realm();

        meta.user_list.forEach(function (user) {
            if (!user.__meta) {
                user.__meta = {};
            }

            user.__meta.checked = false;
        });

        list_render($("#user-checkboxes"), meta.user_list, {
            name: "stream-creation-user-list",
            modifier: function (user) {
                return templates.render('new_stream_users_table', {
                    user: user,
                    checked: user.__meta.checked,
                });
            },
            filter: {
                element: $(".add-user-list-filter"),
                callback: function (item, value) {
                    return (
                        item.email.toLocaleLowerCase().indexOf(value) > -1 ||
                        item.full_name.toLocaleLowerCase().indexOf(value) > -1
                    );
                },
                onupdate: function () {
                    // ui.update_scrollbar(dropdown_list_body);
                },
            },
        }).init();

        // Make the options default to the same each time:
        // public, "announce stream" on.
        $('#make-invite-only input:radio[value=public]').prop('checked', true);

        if (page_params.notifications_stream) {
            $('#announce-new-stream').show();
            $('#announce-new-stream input').prop('disabled', false);
            $('#announce-new-stream input').prop('checked', true);
        } else {
            $('#announce-new-stream').hide();
        }

        stream_name_error.clear_errors();

        $("#stream-checkboxes label.checkbox").on('change', function (e) {
            var elem = $(this);
            var stream_id = elem.attr('data-stream-id');
            var checked = elem.find('input').prop('checked');
            var subscriber_ids = stream_data.get_sub_by_id(stream_id).subscribers;

            $('#user-checkboxes label.checkbox').each(function () {
                var user_elem = $(this);
                var user_id = user_elem.attr('data-user-id');

                if (subscriber_ids.has(user_id)) {
                    user_elem.find('input').prop('checked', checked);
                }
            });

            update_announce_stream_state();
            e.preventDefault();
        });
    };

    exports.show_new_stream_modal.check_all_users = function () {
        meta.modified_user_list.forEach(function (user) { user.__meta.checked = true; });
        list_render.get("stream-creation-user-list").clear().render();
    };

    exports.show_new_stream_modal.uncheck_all_users = function () {
        meta.modified_user_list.forEach(function (user) { user.__meta.checked = false; });
        list_render.get("stream-creation-user-list").clear().render();
    };

    exports.show_new_stream_modal.modified_user_list = function () {
        return meta.user_list;
    };
}());

$(function () {
    $('body').on('change', '#user-checkboxes input, #make-invite-only input', update_announce_stream_state);

    // 'Check all' and 'Uncheck all' visible users
    $(document).on('click', '.subs_set_all_users', function (e) {
        exports.show_new_stream_modal.check_all_users();
        $('#user-checkboxes .checkbox').each(function (idx, li) {
            if  (li.style.display !== "none") {
                $(li.firstElementChild).prop('checked', true);
            }
        });
        e.preventDefault();
        update_announce_stream_state();
    });

    $(document).on('click', '.subs_unset_all_users', function (e) {
        exports.show_new_stream_modal.uncheck_all_users();
        $('#user-checkboxes .checkbox').each(function (idx, li) {
            if  (li.style.display !== "none") {
                $(li.firstElementChild).prop('checked', false);
            }
        });
        e.preventDefault();
        update_announce_stream_state();
    });

    $(document).on("change", "#user-checkboxes label.checkbox", function () {
        var user_id = parseInt($(this).data("user-id"), 10);
        var checked = this.querySelector("input").checked;
        var user = _.find(exports.show_new_stream_modal.modified_user_list(), function (item) {
            return item.user_id === user_id;
        });

        user.__meta.checked = checked;
    });

    $(document).on('click', '#copy-from-stream-expand-collapse', function (e) {
        $('#stream-checkboxes').toggle();
        $("#copy-from-stream-expand-collapse .toggle").toggleClass('icon-vector-caret-right icon-vector-caret-down');
        e.preventDefault();
        update_announce_stream_state();
    });

    $(".subscriptions").on("submit", "#stream_creation_form", function (e) {
        e.preventDefault();
        var stream_name = $.trim($("#create_stream_name").val());
        var name_ok = stream_name_error.validate_for_submit(stream_name);

        if (!name_ok) {
            return;
        }

        var principals = get_principals();
        if (principals.length >= 50) {
            var invites_warning_modal = templates.render('subscription_invites_warning_modal',
                                                         {stream_name: stream_name,
                                                          count: principals.length});
            $('#stream-creation').append(invites_warning_modal);
        } else {
            create_stream();
        }
    });

    $(document).on("click", ".close-invites-warning-modal", function () {
        $("#invites-warning-overlay").remove();
    });

    $(document).on("click", ".confirm-invites-warning-modal", function () {
        create_stream();
        $("#invites-warning-overlay").remove();
    });

    $(".subscriptions").on("input", "#create_stream_name", function () {
        var stream_name = $.trim($("#create_stream_name").val());

        // This is an inexpensive check.
        stream_name_error.pre_validate(stream_name);
    });

    $("body").on("mouseover", "#announce-stream-docs", function (e) {
        var announce_stream_docs = $("#announce-stream-docs");
        announce_stream_docs.popover({placement: "right",
                                      content: templates.render('announce_stream_docs'),
                                      trigger: "manual"});
        announce_stream_docs.popover('show');
        announce_stream_docs.data('popover').tip().css('z-index', 2000);
        announce_stream_docs.data('popover').tip().find('.popover-content').css('margin', '9px 14px');
        e.stopPropagation();
    });
    $("body").on("mouseout", "#announce-stream-docs", function (e) {
        $("#announce-stream-docs").popover('hide');
        e.stopPropagation();
    });

});

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = stream_create;
}
