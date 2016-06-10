var subs = (function () {

var exports = {};

function add_admin_options(sub) {
    return _.extend(sub, {
        'is_admin': page_params.is_admin,
        'can_make_public': page_params.is_admin && sub.invite_only && stream_data.is_subscribed(sub.name),
        'can_make_private': page_params.is_admin && !sub.invite_only
    });
}

function get_color() {
    var used_colors = stream_data.get_colors();
    var color = stream_color.pick_color(used_colors);
    return color;
}

function selectText(element) {
  var range, sel;
    if (window.getSelection) {
        sel = window.getSelection();
        range = document.createRange();
        range.selectNodeContents(element);

        sel.removeAllRanges();
        sel.addRange(range);
    } else if (document.body.createTextRange) {
        range = document.body.createTextRange();
        range.moveToElementText(element);
        range.select();
    }
}

function should_list_all_streams() {
    return page_params.domain !== 'mit.edu';
}

exports.stream_id = function (stream_name) {
    var sub = stream_data.get_sub(stream_name);
    if (sub === undefined) {
        blueslip.error("Tried to get subs.stream_id for a stream user is not subscribed to!");
        return 0;
    }
    return parseInt(sub.stream_id, 10);
};

function set_stream_property(stream_name, property, value) {
    var sub_data = {stream: stream_name, property: property, value: value};
    return channel.post({
        url:      '/json/subscriptions/property',
        data: {"subscription_data": JSON.stringify([sub_data])},
        timeout:  10*1000
    });
}

function set_notification_setting_for_all_streams(notification_type, new_setting) {
    _.each(stream_data.subscribed_subs(), function (sub) {
        if (sub[notification_type] !== new_setting) {
            set_stream_property(sub.name, notification_type, new_setting);
        }
    });
}

exports.set_all_stream_desktop_notifications_to = function (new_setting) {
    set_notification_setting_for_all_streams("desktop_notifications", new_setting);
};

exports.set_all_stream_audible_notifications_to = function (new_setting) {
    set_notification_setting_for_all_streams("audible_notifications", new_setting);
};

function stream_home_view_clicked(e) {
    var sub_row = $(e.target).closest('.subscription_row');
    var stream = sub_row.find('.subscription_name').text();
    var sub = stream_data.get_sub(stream);
    var notification_checkboxes = sub_row.find(".sub_notification_setting");

    subs.toggle_home(stream);

    if (sub.in_home_view) {
        sub_row.find(".mute-note").addClass("hide-mute-note");
        notification_checkboxes.removeClass("muted-sub");
        notification_checkboxes.find("input[type='checkbox']").removeAttr("disabled");
    } else {
        sub_row.find(".mute-note").removeClass("hide-mute-note");
        notification_checkboxes.addClass("muted-sub");
        notification_checkboxes.find("input[type='checkbox']").attr("disabled", true);
    }
}

function update_in_home_view(sub, value) {
    sub.in_home_view = value;

    setTimeout(function () {
        var msg_offset, saved_ypos;
        // Save our current scroll position
        if (ui.home_tab_obscured()) {
            saved_ypos = viewport.scrollTop();
        } else if (home_msg_list === current_msg_list &&
                   current_msg_list.selected_row().offset() !== null) {
            msg_offset = current_msg_list.selected_row().offset().top;
        }

        home_msg_list.clear({clear_selected_id: false});

        // Recreate the home_msg_list with the newly filtered message_list.all
        message_store.add_messages(message_list.all.all_messages(), home_msg_list);

        // Ensure we're still at the same scroll position
        if (ui.home_tab_obscured()) {
            viewport.scrollTop(saved_ypos);
        } else if (home_msg_list === current_msg_list) {
            // We pass use_closest to handle the case where the
            // currently selected message is being hidden from the
            // home view
            home_msg_list.select_id(home_msg_list.selected_id(),
                                    {use_closest: true, empty_ok: true});
            if (current_msg_list.selected_id() !== -1) {
                viewport.set_message_offset(msg_offset);
            }
        }

        // In case we added messages to what's visible in the home view, we need to re-scroll to make
        // sure the pointer is still visible. We don't want the auto-scroll handler to move our pointer
        // to the old scroll location before we have a chance to update it.
        pointer.recenter_pointer_on_display = true;
        pointer.suppress_scroll_pointer_update = true;

        if (! home_msg_list.empty()) {
            process_loaded_for_unread(home_msg_list.all_messages());
        }
    }, 0);

    stream_list.set_in_home_view(sub.name, sub.in_home_view);

    var not_in_home_view_checkbox = $("#subscription_" + sub.stream_id + " #sub_setting_not_in_home_view .sub_setting_control");
    not_in_home_view_checkbox.attr('checked', !value);
}

exports.toggle_home = function (stream_name) {
    var sub = stream_data.get_sub(stream_name);
    update_in_home_view(sub, ! sub.in_home_view);
    set_stream_property(stream_name, 'in_home_view', sub.in_home_view);
};

function update_stream_desktop_notifications(sub, value) {
    var desktop_notifications_checkbox = $("#subscription_" + sub.stream_id + " #sub_desktop_notifications_setting .sub_setting_control");
    desktop_notifications_checkbox.attr('checked', value);
    sub.desktop_notifications = value;
}

function update_stream_audible_notifications(sub, value) {
    var audible_notifications_checkbox = $("#subscription_" + sub.stream_id + " #sub_audible_notifications_setting .sub_setting_control");
    audible_notifications_checkbox.attr('checked', value);
    sub.audible_notifications = value;
}

function update_stream_name(sub, new_name) {
    // Rename the stream internally.
    var old_name = sub.name;
    stream_data.delete_sub(old_name);
    sub.name = new_name;
    stream_data.add_sub(new_name, sub);

    // Update the left sidebar.
    stream_list.rename_stream(sub);

    // Update the message feed.
    _.each([home_msg_list, current_msg_list, message_list.all], function (list) {
        list.change_display_recipient(old_name, new_name);
    });
}

function update_stream_description(sub, description) {
    sub.description = description;

    var sub_settings_selector = '.subscription_row[data-subscription-id=' + sub.stream_id + ']';
    $(sub_settings_selector + ' .subscription_description').text(description);
    $(sub_settings_selector + ' input.description').val(description);
}

function stream_desktop_notifications_clicked(e) {
    var sub_row = $(e.target).closest('.subscription_row');
    var stream = sub_row.find('.subscription_name').text();

    var sub = stream_data.get_sub(stream);
    sub.desktop_notifications = ! sub.desktop_notifications;
    set_stream_property(stream, 'desktop_notifications', sub.desktop_notifications);
}

function stream_audible_notifications_clicked(e) {
    var sub_row = $(e.target).closest('.subscription_row');
    var stream = sub_row.find('.subscription_name').text();

    var sub = stream_data.get_sub(stream);
    sub.audible_notifications = ! sub.audible_notifications;
    set_stream_property(stream, 'audible_notifications', sub.audible_notifications);
}

exports.set_color = function (stream_name, color) {
    var sub = stream_data.get_sub(stream_name);
    stream_color.update_stream_color(sub, stream_name, color, {update_historical: true});
    set_stream_property(stream_name, 'color', color);
};

function create_sub(stream_name, attrs) {
    var sub = stream_data.get_sub(stream_name);
    if (sub !== undefined) {
        // We've already created this subscription, no need to continue.
        return sub;
    }

    if (!attrs.stream_id) {
        // fail fast (blueslip.fatal will throw an error on our behalf)
        blueslip.fatal("We cannot create a sub without a stream_id");
        return; // this line is never actually reached
    }

    // Our internal data structure for subscriptions is mostly plain dictionaries,
    // so we just reuse the attrs that are passed in to us, but we encapsulate how
    // we handle subscribers.
    var subscriber_emails = attrs.subscribers;
    var raw_attrs = _.omit(attrs, 'subscribers');

    sub = _.defaults(raw_attrs, {
        name: stream_name,
        render_subscribers: page_params.domain !== 'mit.edu' || attrs.invite_only === true,
        subscribed: true,
        in_home_view: true,
        invite_only: false,
        desktop_notifications: page_params.stream_desktop_notifications_enabled,
        audible_notifications: page_params.stream_sounds_enabled,
        description: ''
    });

    stream_data.set_subscribers(sub, subscriber_emails);

    if (!sub.color) {
        sub.color = get_color();
    }

    stream_data.add_sub(stream_name, sub);
    $(document).trigger($.Event('sub_obj_created.zulip', {sub: sub}));
    return sub;
}

function button_for_sub(sub) {
    var id = parseInt(sub.stream_id, 10);
    return $("#subscription_" + id + " .sub_unsub_button");
}

function settings_for_sub(sub) {
    var id = parseInt(sub.stream_id, 10);
    return $("#subscription_settings_" + id);
}

exports.show_settings_for = function (stream_name) {
    settings_for_sub(stream_data.get_sub(stream_name)).collapse('show');
};

function add_email_hint(row) {
    // Add a popover explaining stream e-mail addresses on hover.
    var hint_id = "#email-address-hint-" + row.stream_id;
    var email_address_hint = $(hint_id);
    email_address_hint.popover({"placement": "bottom",
                "title": "Email integration",
                "content": templates.render('email_address_hint',
                                            { page_params: page_params }),
                "trigger": "manual"});
    $("body").on("mouseover", hint_id, function (e) {
        email_address_hint.popover('show');
        e.stopPropagation();
    });
    $("body").on("mouseout", hint_id, function (e) {
        email_address_hint.popover('hide');
        e.stopPropagation();
    });
}

function add_sub_to_table(sub) {
    sub = add_admin_options(sub);
    var html = templates.render('subscription', sub);
    $('#create_stream_row').after(html);
    settings_for_sub(sub).collapse('show');
    add_email_hint(sub);
}

function format_member_list_elem(name, email) {
    return templates.render('stream_member_list_entry',
                            {name: name, email: email,
                             displaying_for_admin: page_params.is_admin});
}

function add_element_to_member_list (tb, elem) {
    tb.prepend(elem);
}

function add_to_member_list(tb, name, email) {
    tb.prepend(format_member_list_elem(name, email));
}

exports.mark_subscribed = function (stream_name, attrs) {
    var sub = stream_data.get_sub(stream_name);

    if (sub === undefined) {
        // Create a new stream.
        sub = create_sub(stream_name, attrs);
        add_sub_to_table(sub);
    } else if (! sub.subscribed) {
        // Add yourself to a stream we already know about client-side.
        var color = get_color();
        exports.set_color(stream_name, color);
        sub.subscribed = true;
        sub.subscribers = Dict.from_array(attrs.subscribers);
        var settings = settings_for_sub(sub);
        var button = button_for_sub(sub);
        if (button.length !== 0) {
            button.text(i18n.t("Subscribed")).addClass("subscribed-button").addClass("btn-success");
            // Add the user to the member list if they're currently
            // viewing the members of this stream
            if (sub.render_subscribers && settings.hasClass('in')) {
                var members = settings.find(".subscriber_list_container .subscriber-list");
                add_to_member_list(members, page_params.fullname, page_params.email);
            }
        } else {
            add_sub_to_table(sub);
        }

        // Display the swatch and subscription settings
        var sub_row = settings.closest('.subscription_row');
        sub_row.find(".color_swatch").addClass('in');
        sub_row.find(".regular_subscription_settings").collapse('show');
    } else {
        // Already subscribed
        return;
    }

    if (current_msg_list.narrowed) {
        current_msg_list.update_trailing_bookend();
    }

    // Update unread counts as the new stream in sidebar might
    // need its unread counts re-calculated
    process_loaded_for_unread(message_list.all.all_messages());

    $(document).trigger($.Event('subscription_add_done.zulip', {sub: sub}));
};

exports.mark_unsubscribed = function (stream_name) {
    var sub = stream_data.get_sub(stream_name);
    exports.mark_sub_unsubscribed(sub);
};

exports.mark_sub_unsubscribed = function (sub) {
    if (sub === undefined) {
        // We don't know about this stream
        return;
    } else if (sub.subscribed) {
        stream_list.remove_narrow_filter(sub.name, 'stream');
        sub.subscribed = false;
        button_for_sub(sub).removeClass("subscribed-button").removeClass("btn-success").removeClass("btn-danger").text(i18n.t("Subscribe"));
        var settings = settings_for_sub(sub);
        if (settings.hasClass('in')) {
            settings.collapse('hide');
        }

        // Hide the swatch and subscription settings
        var sub_row = settings.closest('.subscription_row');
        sub_row.find(".color_swatch").removeClass('in');
        if (sub.render_subscribers) {
            // TODO: having a completely empty settings div messes
            // with Bootstrap's collapser.  We currently just ensure
            // that it's not empty on the MIT realm, even though it
            // looks weird
            sub_row.find(".regular_subscription_settings").collapse('hide');
        }
    } else {
        // Already unsubscribed
        return;
    }

    if (current_msg_list.narrowed) {
        current_msg_list.update_trailing_bookend();
    }

    $(document).trigger($.Event('subscription_remove_done.zulip', {sub: sub}));
};

exports.receives_desktop_notifications = function (stream_name) {
    var sub = stream_data.get_sub(stream_name);
    if (sub === undefined) {
        return false;
    }
    return sub.desktop_notifications;
};

exports.receives_audible_notifications = function (stream_name) {
    var sub = stream_data.get_sub(stream_name);
    if (sub === undefined) {
        return false;
    }
    return sub.audible_notifications;
};

function populate_subscriptions(subs, subscribed) {
    var sub_rows = [];
    subs.sort(function (a, b) {
        return util.strcmp(a.name, b.name);
    });
    subs.forEach(function (elem) {
        var stream_name = elem.name;
        var sub = create_sub(stream_name, {color: elem.color, in_home_view: elem.in_home_view,
                                           invite_only: elem.invite_only,
                                           desktop_notifications: elem.desktop_notifications,
                                           audible_notifications: elem.audible_notifications,
                                           subscribed: subscribed,
                                           email_address: elem.email_address,
                                           stream_id: elem.stream_id,
                                           subscribers: elem.subscribers,
                                           description: elem.description});
        sub_rows.push(sub);
    });

    return sub_rows;
}

exports.setup_page = function () {
    loading.make_indicator($('#subs_page_loading_indicator'));

    function _populate_and_fill(public_streams) {

        // Build up our list of subscribed streams from the data we already have.
        var subscribed_rows = stream_data.subscribed_subs();

        // To avoid dups, build a set of names we already subscribed to.
        var subscribed_set = new Dict({fold_case: true});
        _.each(subscribed_rows, function (sub) {
            subscribed_set.set(sub.name, true);
        });

        // Right now the back end gives us all public streams; we really only
        // need to add the ones we haven't already subscribed to.
        var unsubscribed_streams = _.reject(public_streams.streams, function (stream) {
            return subscribed_set.has(stream.name);
        });

        // Build up our list of unsubscribed rows.
        var unsubscribed_rows = [];
        _.each(unsubscribed_streams, function (stream) {
            var sub = stream_data.get_sub(stream.name);
            if (!sub) {
                sub = create_sub(stream.name, _.extend({subscribed: false}, stream));
            }
            unsubscribed_rows.push(sub);
        });

        // Sort and combine all our streams.
        function by_name(a,b) {
            return util.strcmp(a.name, b.name);
        }
        subscribed_rows.sort(by_name);
        unsubscribed_rows.sort(by_name);
        var all_subs = subscribed_rows.concat(unsubscribed_rows);

        // Add in admin options.
        var sub_rows = [];
        _.each(all_subs, function (sub) {
            sub = add_admin_options(sub);
            sub_rows.push(sub);
        });

        $('#subscriptions_table').empty();
        var template_data = {
            can_create_streams: page_params.can_create_streams,
            subscriptions: sub_rows
        };
        var rendered = templates.render('subscription_table_body', template_data);
        $('#subscriptions_table').append(rendered);

        _.each(sub_rows, function (row) {
            add_email_hint(row);
        });

        loading.destroy_indicator($('#subs_page_loading_indicator'));
        $(document).trigger($.Event('subs_page_loaded.zulip'));
    }

    function populate_and_fill(public_streams) {
        i18n.ensure_i18n(function () {
            _populate_and_fill(public_streams);
        });
    }

    function failed_listing(xhr, error) {
        loading.destroy_indicator($('#subs_page_loading_indicator'));
        ui.report_error("Error listing streams or subscriptions", xhr,
                        $("#subscriptions-status"), 'subscriptions-status');
    }

    if (should_list_all_streams()) {
        var req = channel.get({
            url: '/json/streams',
            data: {"include_subscribed": false},
            idempotent: true,
            timeout:  10*1000,
            success: populate_and_fill,
            error: failed_listing
        });
    } else {
        populate_and_fill({streams: []});
        $('#create_stream_button').val(i18n.t("Subscribe"));
    }
};

exports.update_subscription_properties = function (stream_name, property, value) {
    var sub = stream_data.get_sub(stream_name);
    if (sub === undefined) {
        // This isn't a stream we know about, so ignore it.
        blueslip.warn("Update for an unknown subscription", {stream_name: stream_name,
                                                            property: property,
                                                            value: value});
        return;
    }
    switch(property) {
    case 'color':
        stream_color.update_stream_color(sub, stream_name, value, {update_historical: true});
        break;
    case 'in_home_view':
        update_in_home_view(sub, value);
        break;
    case 'desktop_notifications':
        update_stream_desktop_notifications(sub, value);
        break;
    case 'audible_notifications':
        update_stream_audible_notifications(sub, value);
        break;
    case 'name':
        update_stream_name(sub, value);
        break;
    case 'description':
        update_stream_description(sub, value);
        break;
    case 'email_address':
        sub.email_address = value;
        break;
    default:
        blueslip.warn("Unexpected subscription property type", {property: property,
                                                                value: value});
    }
};

function ajaxSubscribe(stream) {
    // Subscribe yourself to a single stream.
    var true_stream_name;

    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {"subscriptions": JSON.stringify([{"name": stream}]) },
        success: function (resp, statusText, xhr, form) {
            $("#create_stream_name").val("");

            var res = $.parseJSON(xhr.responseText);
            if (!$.isEmptyObject(res.already_subscribed)) {
                // Display the canonical stream capitalization.
                true_stream_name = res.already_subscribed[page_params.email][0];
                ui.report_success("Already subscribed to " + true_stream_name,
                                  $("#subscriptions-status"), 'subscriptions-status');
            }
            // The rest of the work is done via the subscribe event we will get
        },
        error: function (xhr) {
            ui.report_error("Error adding subscription", xhr,
                            $("#subscriptions-status"), 'subscriptions-status');
        }
    });
}

function ajaxUnsubscribe(stream) {
    return channel.post({
        url: "/json/subscriptions/remove",
        data: {"subscriptions": JSON.stringify([stream]) },
        success: function (resp, statusText, xhr, form) {
            var name, res = $.parseJSON(xhr.responseText);
            $("#subscriptions-status").hide();
            // The rest of the work is done via the unsubscribe event we will get
        },
        error: function (xhr) {
            ui.report_error("Error removing subscription", xhr,
                            $("#subscriptions-status"), 'subscriptions-status');
        }
    });
}

function ajaxSubscribeForCreation(stream, principals, invite_only, announce) {
    // Subscribe yourself and possible other people to a new stream.
    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {"subscriptions": JSON.stringify([{"name": stream}]),
               "principals": JSON.stringify(principals),
               "invite_only": JSON.stringify(invite_only),
               "announce": JSON.stringify(announce)
        },
        success: function (data) {
            $("#create_stream_name").val("");
            $("#subscriptions-status").hide();
            $('#stream-creation').modal("hide");
            // The rest of the work is done via the subscribe event we will get
        },
        error: function (xhr) {
            ui.report_error("Error creating stream", xhr,
                            $("#subscriptions-status"), 'subscriptions-status');
            $('#stream-creation').modal("hide");
        }
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

function show_new_stream_modal() {
    $('#people_to_add').html(templates.render('new_stream_users', {
        users: people.get_rest_of_realm()
    }));

    // Make the options default to the same each time:
    // public, "announce stream" on.
    $('#make-invite-only input:radio[value=public]').prop('checked', true);
    $('#announce-new-stream input').prop('disabled', false);
    $('#announce-new-stream input').prop('checked', true);

    $('#stream-creation').modal("show");
}

exports.invite_user_to_stream = function (user_email, stream_name, success, failure) {
    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {"subscriptions": JSON.stringify([{"name": stream_name}]),
               "principals": JSON.stringify([user_email])},
        success: success,
        error: failure
    });
};

exports.remove_user_from_stream = function (user_email, stream_name, success, failure) {
    return channel.post({
        url: "/json/subscriptions/remove",
        data: {"subscriptions": JSON.stringify([stream_name]),
               "principals": JSON.stringify([user_email])},
        success: success,
        error: failure
    });
};

function inline_emails_into_subscriber_list(subs, email_dict) {
    // When we get subscriber lists from the back end, they are sent as user ids to
    // save bandwidth, but the legacy JS code wants emails.
    _.each(subs, function (sub) {
        if (sub.subscribers) {
            sub.subscribers = _.map(sub.subscribers, function (subscription) {
                return email_dict[subscription];
            });
        }
    });
}

$(function () {
    var i;

    inline_emails_into_subscriber_list(page_params.subbed_info, page_params.email_dict);
    inline_emails_into_subscriber_list(page_params.unsubbed_info, page_params.email_dict);

    // Populate stream_info with data handed over to client-side template.
    populate_subscriptions(page_params.subbed_info, true);
    populate_subscriptions(page_params.unsubbed_info, false);

    // Garbage collect data structures that were only used for initialization.
    delete page_params.subbed_info;
    delete page_params.unsubbed_info;

    // We build the stream_list now.  It may get re-built again very shortly
    // when new messages come in, but it's fairly quick.
    stream_list.build_stream_list();

    $("#subscriptions_table").on("submit", "#add_new_subscription", function (e) {
        e.preventDefault();

        if (!should_list_all_streams()) {
            ajaxSubscribe($("#create_stream_name").val());
            return;
        }

        var stream = $.trim($("#create_stream_name").val());
        var stream_status = compose.check_stream_existence(stream);
        if (stream_status === "does-not-exist") {
            $("#stream_name").text(stream);
            show_new_stream_modal();
        } else {
            ajaxSubscribe(stream);
        }
    });

    $('#stream_creation_form').on('change',
                                  '#user-checkboxes input, #make-invite-only input',
                                  update_announce_stream_state);

    // 'Check all' and 'Uncheck all' links
    $(document).on('click', '.subs_set_all_users', function (e) {
        $('#people_to_add :checkbox').attr('checked', true);
        e.preventDefault();
        update_announce_stream_state();
    });
    $(document).on('click', '.subs_unset_all_users', function (e) {
        $('#people_to_add :checkbox').attr('checked', false);
        e.preventDefault();
        update_announce_stream_state();
    });

    var announce_stream_docs = $("#announce-stream-docs");
    announce_stream_docs.popover({"placement": "right",
                                  "content": templates.render('announce_stream_docs'),
                                  "trigger": "manual"});
    $("body").on("mouseover", "#announce-stream-docs", function (e) {
        announce_stream_docs.popover('show');
        announce_stream_docs.data('popover').tip().css('z-index', 2000);
        e.stopPropagation();
    });
    $("body").on("mouseout", "#announce-stream-docs", function (e) {
        announce_stream_docs.popover('hide');
        e.stopPropagation();
    });

    $("#stream_creation_form").on("submit", function (e) {
        e.preventDefault();
        var stream = $.trim($("#create_stream_name").val());
        var principals = _.map(
            $("#stream_creation_form input:checkbox[name=user]:checked"),
            function (elem) {
                return $(elem).val();
            }
        );
        // You are always subscribed to streams you create.
        principals.push(page_params.email);
        ajaxSubscribeForCreation(stream,
            principals,
            $('#stream_creation_form input[name=privacy]:checked').val() === "invite-only",
            $('#announce-new-stream input').prop('checked')
            );
    });

    $("body").on("mouseover", ".subscribed-button", function (e) {
        $(e.target).addClass("btn-danger").text(i18n.t("Unsubscribe"));
    }).on("mouseout", ".subscribed-button", function (e) {
        $(e.target).removeClass("btn-danger").text(i18n.t("Subscribed"));
    });

    $("#subscriptions-status").on("click", "#close-subscriptions-status", function (e) {
        $("#subscriptions-status").hide();
    });

    $("#subscriptions_table").on("click", ".email-address", function (e) {
        selectText(this);
    });

    $("#subscriptions_table").on("click", ".sub_unsub_button", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var sub_row = $(e.target).closest('.subscription_row');
        var stream_name = sub_row.find('.subscription_name').text();
        var sub = stream_data.get_sub(stream_name);

        if (sub.subscribed) {
            ajaxUnsubscribe(stream_name);
        } else {
            ajaxSubscribe(stream_name);
        }
    });

    $("#zfilt").on("click", ".stream_sub_unsub_button", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var stream_name = narrow.stream();
        if (stream_name === undefined) {
            return;
        }
        var sub = stream_data.get_sub(stream_name);

        if (sub.subscribed) {
            ajaxUnsubscribe(stream_name);
        } else {
            ajaxSubscribe(stream_name);
        }
    });

    $('.empty_feed_sub_unsub').click(function (e) {
        e.preventDefault();

        $('#subscription-status').hide();
        var stream_name = narrow.stream();
        if (stream_name === undefined) {
            return;
        }
        var sub = stream_data.get_sub(stream_name);

        if (sub.subscribed) {
            ajaxUnsubscribe(stream_name);
        } else {
            ajaxSubscribe(stream_name);
        }
        $('.empty_feed_notice').hide();
        $('#empty_narrow_message').show();
    });

    $("#subscriptions_table").on("show", ".subscription_settings", function (e) {
        var subrow = $(e.target).closest('.subscription_row');
        var colorpicker = subrow.find('.colorpicker');

        var color = stream_data.get_color(subrow.find('.subscription_name').text());
        stream_color.set_colorpicker_color(colorpicker, color);

        // To figure out the worst case for an expanded row's height, we do some math:
        // .subscriber_list_container max-height,
        // .subscriber_list_settings,
        // .regular_subscription_settings
        // .subscription_header line-height,
        // .subscription_header padding
        var expanded_row_size = 200 + 30 + 100 + 30 + 5;
        var cover = subrow.offset().top + expanded_row_size -
            viewport.height() + viewport.scrollTop();
        if (cover > 0) {
            $('.app').animate({
                scrollTop: viewport.scrollTop() + cover + 5
            });
        }

        // Make all inputs have a default tabindex
        subrow.find('.subscription_settings :input').removeAttr('tabindex');
    });

    $("#subscriptions_table").on("hide", ".subscription_settings", function (e) {
        var subrow = $(e.target).closest('.subscription_row');

        // Remove all inputs from the tabindex
        subrow.find('.subscription_settings :input').attr('tabindex', '-1');
    });

    $("#subscriptions_table").on("click", ".sub_setting_checkbox", function (e) {
        var control = $(e.target).closest('.sub_setting_checkbox').find('.sub_setting_control');
        // A hack.  Don't change the state of the checkbox if we
        // clicked on the checkbox itself.
        if (control[0] !== e.target) {
            control.prop("checked", ! control.prop("checked"));
        }
    });
    $("#subscriptions_table").on("click", "#sub_setting_not_in_home_view", stream_home_view_clicked);
    $("#subscriptions_table").on("click", "#sub_desktop_notifications_setting",
                                 stream_desktop_notifications_clicked);
    $("#subscriptions_table").on("click", "#sub_audible_notifications_setting",
                                 stream_audible_notifications_clicked);

    $("#subscriptions_table").on("submit", ".subscriber_list_add form", function (e) {
        e.preventDefault();
        var sub_row = $(e.target).closest('.subscription_row');
        var stream = sub_row.find('.subscription_name').text();
        var text_box = sub_row.find('input[name="principal"]');
        var principal = $.trim(text_box.val());
        // TODO: clean up this error handling
        var error_elem = sub_row.find('.subscriber_list_container .alert-error');
        var warning_elem = sub_row.find('.subscriber_list_container .alert-warning');
        var list = sub_row.find('.subscriber_list_container .subscriber-list');

        function invite_success(data) {
            text_box.val('');

            if (data.subscribed.hasOwnProperty(principal)) {
                error_elem.addClass("hide");
                warning_elem.addClass("hide");
                if (util.is_current_user(principal)) {
                    // mark_subscribed adds the user to the member list
                    exports.mark_subscribed(stream);
                } else {
                    add_to_member_list(list, people.get_by_email(principal).full_name, principal);
                }
            } else {
                error_elem.addClass("hide");
                warning_elem.removeClass("hide").text("User already subscribed");
            }
        }

        function invite_failure(xhr) {
            warning_elem.addClass("hide");
            error_elem.removeClass("hide").text("Could not add user to this stream");
        }

        exports.invite_user_to_stream(principal, stream, invite_success, invite_failure);
    });

    $("#subscriptions_table").on("submit", ".subscriber_list_remove form", function (e) {
        e.preventDefault();

        var list_entry = $(e.target).closest("tr");
        var principal = list_entry.children(".subscriber-email").text();
        var sub_row = $(e.target).closest('.subscription_row');
        var stream_name = sub_row.find('.subscription_name').text();
        var error_elem = sub_row.find('.subscriber_list_container .alert-error');
        var warning_elem = sub_row.find('.subscriber_list_container .alert-warning');

        function removal_success(data) {
            if (data.removed.length > 0) {
                error_elem.addClass("hide");
                warning_elem.addClass("hide");

                // Remove the user from the subscriber list.
                list_entry.remove();

                if (util.is_current_user(principal)) {
                    // If you're unsubscribing yourself, mark whole
                    // stream entry as you being unsubscribed.
                    exports.mark_unsubscribed(stream_name);
                }
            } else {
                error_elem.addClass("hide");
                warning_elem.removeClass("hide").text("User already not subscribed");
            }
        }

        function removal_failure(xhr) {
            warning_elem.addClass("hide");
            error_elem.removeClass("hide").text("Could not remove user from this stream");
        }

        exports.remove_user_from_stream(principal, stream_name, removal_success,
                                        removal_failure);
    });

    $("#subscriptions_table").on("submit", ".rename-stream form", function (e) {
        e.preventDefault();

        var sub_row = $(e.target).closest('.subscription_row');
        var old_name_box = sub_row.find('.subscription_name');
        var old_name = old_name_box.text();
        var new_name_box = sub_row.find('input[name="new-name"]');
        var new_name = $.trim(new_name_box.val());

        $("#subscriptions-status").hide();

        channel.post({
            url: "/json/rename_stream",
            data: {"old_name": old_name, "new_name": new_name},
            success: function (data) {
                new_name_box.val('');
                // Update all visible instances of the old name to the new name.
                old_name_box.text(new_name);
                sub_row.find(".email-address").text(data.email_address);

                ui.report_success("The stream has been renamed!", $("#subscriptions-status "),
                                  'subscriptions-status');
            },
            error: function (xhr) {
                ui.report_error("Error renaming stream", xhr,
                                $("#subscriptions-status"), 'subscriptions-status');
            }
        });
    });

    $('#subscriptions_table').on('submit', '.change-stream-description form', function (e) {
        e.preventDefault();
        var $form = $(e.target);

        var $sub_row = $(e.target).closest('.subscription_row');
        var stream_name = $sub_row.find('.subscription_name').text();
        var description = $sub_row.find('input[name="description"]').val();

        $('#subscriptions-status').hide();

        channel.patch({
            url: '/json/streams/' + stream_name,
            data: {
                'description': JSON.stringify(description)
            },
            success: function () {
                // The event from the server will update the rest of the UI
                ui.report_success("The stream description has been updated!",
                                 $("#subscriptions-status"), 'subscriptions-status');
            },
            error: function (xhr) {
                ui.report_error("Error updating the stream description", xhr,
                                $("#subscriptions-status"), 'subscriptions-status');
            }
        });
    });

    function redraw_privacy_related_stuff(sub_row, sub) {
        var html;

        sub = add_admin_options(sub);

        html = templates.render('subscription_setting_icon', sub);
        sub_row.find('.subscription-setting-icon').expectOne().html(html);

        html = templates.render('subscription_type', sub);
        sub_row.find('.subscription-type').expectOne().html(html);

        html = templates.render('change_stream_privacy', sub);
        sub_row.find('.change-stream-privacy').expectOne().html(html);

        stream_list.redraw_stream_privacy(sub.name);
    }

    function change_stream_privacy(e, url, success_message, error_message, invite_only) {
        e.preventDefault();

        var stream_name = $(e.target).attr("data-stream-name");
        var sub_row = $(e.target).closest('.subscription_row');

        $("#subscriptions-status").hide();
        var data = {"stream_name": stream_name};

        channel.post({
            url: url,
            data: data,
            success: function (data) {
                var sub = stream_data.get_sub(stream_name);
                sub.invite_only = invite_only;
                redraw_privacy_related_stuff(sub_row, sub);
                var feedback_div = sub_row.find(".change-stream-privacy-feedback").expectOne();
                ui.report_success(success_message, feedback_div);
            },
            error: function (xhr) {
                var feedback_div = sub_row.find(".change-stream-privacy-feedback").expectOne();
                ui.report_error(error_message, xhr, feedback_div);
            }
        });
    }

    $("#subscriptions_table").on("click", ".make-stream-public-button", function (e) {
        change_stream_privacy(
            e,
            "/json/make_stream_public",
            "The stream has been made public!",
            "Error making stream public",
            false
        );
    });

    $("#subscriptions_table").on("click", ".make-stream-private-button", function (e) {
        change_stream_privacy(
            e,
            "/json/make_stream_private",
            "The stream has been made private!",
            "Error making stream private",
            true
        );
    });

    $("#subscriptions_table").on("show", ".regular_subscription_settings", function (e) {
        // We want 'show' events that originate from
        // 'regular_subscription_settings' divs not to trigger the
        // handler for the entire subscription_settings div
        e.stopPropagation();
    });

    $("#subscriptions_table").on("show", ".subscription_settings", function (e) {
        var sub_row = $(e.target).closest('.subscription_row');
        var stream = sub_row.find('.subscription_name').text();
        var warning_elem = sub_row.find('.subscriber_list_container .alert-warning');
        var error_elem = sub_row.find('.subscriber_list_container .alert-error');
        var list = sub_row.find('.subscriber_list_container .subscriber-list');
        var indicator_elem = sub_row.find('.subscriber_list_loading_indicator');

        if (!stream_data.get_sub(stream).render_subscribers) {
            return;
        }

        warning_elem.addClass('hide');
        error_elem.addClass('hide');
        list.empty();

        loading.make_indicator(indicator_elem);

        channel.post({
            url: "/json/get_subscribers",
            idempotent: true,
            data: {stream: stream},
            success: function (data) {
                loading.destroy_indicator(indicator_elem);
                var subscribers = _.map(data.subscribers, function (elem) {
                    var person = people.get_by_email(elem);
                    if (person === undefined) {
                        return elem;
                    }
                    return format_member_list_elem(people.get_by_email(elem).full_name, elem);
                });
                _.each(subscribers.sort().reverse(), function (elem) {
                    // add_element_to_member_list *prepends* the element,
                    // so we need to sort in reverse order for it to
                    // appear in alphabetical order.
                    add_element_to_member_list(list, elem);
                });
            },
            error: function (xhr) {
                loading.destroy_indicator(indicator_elem);
                error_elem.removeClass("hide").text("Could not fetch subscriber list");
            }
        });

        sub_row.find('input[name="principal"]').typeahead({
            source: page_params.people_list,
            items: 5,
            highlighter: function (item) {
                var item_formatted = typeahead_helper.render_person(item);
                return typeahead_helper.highlight_with_escaping(this.query, item_formatted);
            },
            matcher: function (item) {
                var query = $.trim(this.query.toLowerCase());
                if (query === '' || query === item.email) {
                    return false;
                }
                // Case-insensitive.
                return (item.email.toLowerCase().indexOf(query) !== -1) ||
                    (item.full_name.toLowerCase().indexOf(query) !== -1);
            },
            sorter: typeahead_helper.sort_recipientbox_typeahead,
            updater: function (item) {
                return item.email;
            }
        });
    });

    // Change the down arrow to an up arrow on expansion, and back to a down
    // arrow on collapse.
    // FIXME: If there's a way, it may be better to do this in pure CSS.
    $("#subscriptions_table").on("show", ".subscription_settings", function (e) {
        var sub_arrow = $(e.target).closest('.subscription_row').find('.sub_arrow i');
        sub_arrow.removeClass('icon-vector-chevron-down');
        sub_arrow.addClass('icon-vector-chevron-up');
    });
    $("#subscriptions_table").on("hide", ".subscription_settings", function (e) {
        var sub_arrow = $(e.target).closest('.subscription_row').find('.sub_arrow i');
        sub_arrow.removeClass('icon-vector-chevron-up');
        sub_arrow.addClass('icon-vector-chevron-down');
    });
});

function focus_on_narrowed_stream() {
    var stream_name = narrow.stream();
    if (stream_name === undefined) {
        return;
    }
    var sub = stream_data.get_sub(stream_name);
    if (sub !== undefined) {
        // This stream is in the list, so focus on it.
        $('html, body').animate({
            scrollTop: settings_for_sub(sub).offset().top
        });
    } else {
        // This stream doesn't exist, so prep for creating it.
        $("#create_stream_name").val(stream_name);
    }
}

exports.show_and_focus_on_narrow = function () {
    $(document).one('subs_page_loaded.zulip', focus_on_narrowed_stream);
    ui.change_tab_to("#subscriptions");
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = subs;
}
