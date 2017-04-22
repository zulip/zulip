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

function ajaxSubscribeForCreation(stream, description, principals, invite_only, announce) {
    // Subscribe yourself and possible other people to a new stream.
    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([{name: stream, description: description}]),
               principals: JSON.stringify(principals),
               invite_only: JSON.stringify(invite_only),
               announce: JSON.stringify(announce),
        },
        success: function () {
            $("#create_stream_name").val("");
            $("#create_stream_description").val("");
            $("#subscriptions-status").hide();
            // The rest of the work is done via the subscribe event we will get
        },
        error: function (xhr) {
            ui_report.error(i18n.t("Error creating stream"), xhr,
                            $("#subscriptions-status"), 'subscriptions-status');
        },
    });
}

// Within the new stream modal...
function update_announce_stream_state() {
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
}

exports.new_stream_clicked = function (stream) {
    // this changes the tab switcher (settings/preview) which isn't necessary
    // to a add new stream title.
    $(".display-type #add_new_stream_title").show();
    $(".display-type #stream_settings_title").hide();

    $(".stream-row.active").removeClass("active");

    $("#stream_settings_title, .subscriptions-container .settings, .nothing-selected").hide();
    $("#stream-creation, #add_new_stream_title").show();

    if (stream !== '') {
        $('#create_stream_name').val(stream);
    }
    exports.show_new_stream_modal();

    // at less than 700px we have a @media query that when you tap the
    // #create_stream_button, the stream prompt slides in. However, when you
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

// *Synchronously* check if a stream exists.
// This is deprecated and we hope to remove it.
exports.check_stream_existence = function (stream_name, autosubscribe) {
    var result = "error";
    var request = {stream: stream_name};
    if (autosubscribe) {
        request.autosubscribe = true;
    }
    channel.post({
        url: "/json/subscriptions/exists",
        data: request,
        async: false,
        success: function (data) {
            if (data.subscribed) {
                result = "subscribed";
            } else {
                result = "not-subscribed";
            }
        },
        error: function (xhr) {
            if (xhr.status === 404) {
                result = "does-not-exist";
            } else {
                result = "error";
            }
        },
    });
    return result;
};


exports.show_new_stream_modal = function () {
    $("#stream-creation").removeClass("hide");
    $(".right .settings").hide();
    $('#people_to_add').html(templates.render('new_stream_users', {
        users: people.get_rest_of_realm(),
        streams: stream_data.get_streams_for_settings_page(),
    }));

    // Make the options default to the same each time:
    // public, "announce stream" on.
    $('#make-invite-only input:radio[value=public]').prop('checked', true);
    $('#announce-new-stream input').prop('disabled', false);
    $('#announce-new-stream input').prop('checked', true);

    $("#stream_name_error").hide();

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

$(function () {
    $('body').on('change', '#user-checkboxes input, #make-invite-only input', update_announce_stream_state);

    // 'Check all' and 'Uncheck all' visible users
    $(document).on('click', '.subs_set_all_users', function (e) {
        $('#user-checkboxes .checkbox').each(function (idx, li) {
            if  (li.style.display !== "none") {
                $(li.firstElementChild).prop('checked', true);
            }
        });
        e.preventDefault();
        update_announce_stream_state();
    });

    $(document).on('click', '.subs_unset_all_users', function (e) {
        $('#user-checkboxes .checkbox').each(function (idx, li) {
            if  (li.style.display !== "none") {
                $(li.firstElementChild).prop('checked', false);
            }
        });
        e.preventDefault();
        update_announce_stream_state();
    });

    $(document).on('click', '#copy-from-stream-expand-collapse', function (e) {
        $('#stream-checkboxes').toggle();
        $("#copy-from-stream-expand-collapse .toggle").toggleClass('icon-vector-caret-right icon-vector-caret-down');
        e.preventDefault();
        update_announce_stream_state();
    });

    // Search People or Streams
    $(document).on('input', '.add-user-list-filter', function (e) {
        var user_list = $(".add-user-list-filter");
        if (user_list === 0) {
            return;
        }
        var search_term = user_list.expectOne().val().trim();
        var search_terms = search_term.toLowerCase().split(",");

        (function filter_user_checkboxes() {
            var user_labels = $("#user-checkboxes label.add-user-label");

            if (search_term === '') {
                user_labels.css({display: 'block'});
                return;
            }

            var users = people.get_rest_of_realm();
            var filtered_users = people.filter_people_by_search_terms(users, search_terms);

            // Be careful about modifying the follow code.  A naive implementation
            // will work very poorly with a large user population (~1000 users).
            //
            // I tested using: `./manage.py populate_db --extra-users 3500`
            //
            // This would break the previous implementation, whereas the new
            // implementation is merely sluggish.
            user_labels.each(function () {
                var elem = $(this);
                var user_id = elem.attr('data-user-id');
                var user_checked = filtered_users.has(user_id);
                var display = user_checked ? "block" : "none";
                elem.css({display: display});
            });
        }());

        update_announce_stream_state();
        e.preventDefault();
    });

    $(".subscriptions").on("submit", "#stream_creation_form", function (e) {
        e.preventDefault();
        var stream = $.trim($("#create_stream_name").val());
        var description = $.trim($("#create_stream_description").val());
        if (!$("#stream_name_error").is(":visible")) {
            var principals = _.map(
                $("#stream_creation_form input:checkbox[name=user]:checked"),
                function (elem) {
                    return $(elem).val();
                }
            );

            // You are always subscribed to streams you create.
            principals.push(people.my_current_email());

            created_stream = stream;

            ajaxSubscribeForCreation(stream,
                description,
                principals,
                $('#stream_creation_form input[name=privacy]:checked').val() === "invite-only",
                $('#announce-new-stream input').prop('checked')
            );
        }
    });

    $(".subscriptions").on("focusout", "#create_stream_name", function () {
        var stream = $.trim($("#create_stream_name").val());
        if (stream.length !== 0) {
            var stream_status = exports.check_stream_existence(stream);

            if (stream_status !== "does-not-exist") {
                $("#stream_name_error").text(i18n.t("A stream with this name already exists"));
                $("#stream_name_error").show();
            } else {
                $("#stream_name_error").hide();
            }
        } else {
            $("#stream_name_error").text(i18n.t("A stream needs to have a name"));
            $("#stream_name_error").show();
        }
    });

    $("body").on("mouseover", "#announce-stream-docs", function (e) {
        var announce_stream_docs = $("#announce-stream-docs");
        announce_stream_docs.popover({placement: "right",
                                      content: templates.render('announce_stream_docs'),
                                      trigger: "manual"});
        announce_stream_docs.popover('show');
        announce_stream_docs.data('popover').tip().css('z-index', 2000);
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
