var pm_list = (function () {

var exports = {};

var private_messages_open = false;

// You can click on "more conversations" to zoom in.  There's no
// way to zoom back out other than re-narrowing out and in of the
// PM list.
var zoomed_in = false;

// This module manages the "Private Messages" section in the upper
// left corner of the app.  This was split out from stream_list.js.

function get_filter_li() {
    return $("#global_filters > li[data-name='private']");
}

function update_count_in_dom(count_span, value_span, count) {
    if (count === 0) {
        count_span.hide();
        value_span.text('');
    } else {
        count_span.show();
        value_span.text(count);
    }
}

function set_count(count) {
    var count_span = get_filter_li().find('.count');
    var value_span = count_span.find('.value');
    update_count_in_dom(count_span, value_span, count);
}

exports.get_conversation_li = function (conversation) {
    // conversation is something like "foo@example.com,bar@example.com"
    var user_ids_string = people.emails_strings_to_user_ids_string(conversation);
    if (!user_ids_string) {
        blueslip.warn('Unknown conversation: ' + conversation);
        return;
    }
    return exports.get_li_for_user_ids_string(user_ids_string);
};

exports.get_li_for_user_ids_string = function (user_ids_string) {
    var pm_li = get_filter_li();
    var convo_li = pm_li.find("li[data-user-ids-string='" + user_ids_string + "']");
    return convo_li;
};

function set_pm_conversation_count(user_ids_string, count) {
    var pm_li = pm_list.get_li_for_user_ids_string(user_ids_string);
    var count_span = pm_li.find('.private_message_count');
    var value_span = count_span.find('.value');

    if (count_span.length === 0 || value_span.length === 0) {
        return;
    }

    count_span.removeClass("zero_count");
    update_count_in_dom(count_span, value_span, count);
}

function remove_expanded_private_messages() {
    stream_popover.hide_topic_popover();
    $("ul.expanded_private_messages").remove();
    resize.resize_stream_filters_container();
}

function zoom_in() {
    zoomed_in = true;
    var list_widget = $("ul.expanded_private_messages").expectOne();
    list_widget.removeClass("zoomed-out").addClass("zoomed-in");
}

exports.close = function () {
    private_messages_open = false;
    zoomed_in = false;
    remove_expanded_private_messages();
};

exports._build_private_messages_list = function (active_conversation, max_private_messages) {

    var private_messages = pm_conversations.recent.get();
    var display_messages = [];
    var hiding_messages = false;

    // SHIM
    if (active_conversation) {
        active_conversation = people.emails_strings_to_user_ids_string(active_conversation);
    }

    _.each(private_messages, function (private_message_obj, idx) {
        var user_ids_string = private_message_obj.user_ids_string;
        var reply_to = people.user_ids_string_to_emails_string(user_ids_string);
        var recipients_string = people.get_recipients(user_ids_string);

        var num_unread = unread.num_unread_for_person(user_ids_string);

        var always_visible = (idx < max_private_messages) || (num_unread > 0)
            || (user_ids_string === active_conversation);

        if (!always_visible) {
            if (!zoomed_in) {
                hiding_messages = true;
            }
        }

        var display_message = {
            recipients: recipients_string,
            user_ids_string: user_ids_string,
            unread: num_unread,
            is_zero: num_unread === 0,
            zoom_out_hide: !always_visible,
            url: narrow.pm_with_uri(reply_to),
        };
        display_messages.push(display_message);
    });

    var zoom_class;

    if (zoomed_in) {
        zoom_class = "zoomed-in";
    } else {
        zoom_class = "zoomed-out";
    }

    var recipients_dom = templates.render('sidebar_private_message_list',
                                  {messages: display_messages,
                                   zoom_class: zoom_class,
                                   want_show_more_messages_links: hiding_messages});
    return recipients_dom;
};

exports.rebuild_recent = function (active_conversation) {
    remove_expanded_private_messages();
    if (private_messages_open) {
        var max_private_messages = 5;
        var private_li = get_filter_li();
        var private_messages_dom = exports._build_private_messages_list(active_conversation,
            max_private_messages);

        private_li.append(private_messages_dom);
    }
    if (active_conversation) {
        var active_li = exports.get_conversation_li(active_conversation);
        if (active_li) {
            active_li.addClass('active-sub-filter');
        }
    }

    resize.resize_stream_filters_container();
};

exports.update_private_messages = function () {
    exports._build_private_messages_list();

    if (! narrow_state.active()) {
        return;
    }

    var is_pm_filter = _.contains(narrow_state.filter().operands('is'), "private");
    var conversation = narrow_state.filter().operands('pm-with');
    if (conversation.length === 1) {
        exports.rebuild_recent(conversation[0]);
    } else if (conversation.length !== 0) {
        // TODO: This should be the reply-to of the thread.
        exports.rebuild_recent("");
    } else if (is_pm_filter) {
        exports.rebuild_recent("");
        $("#global_filters li[data-name='private']").addClass('active-filter');
    }
};

exports.set_click_handlers = function () {
    $('#global_filters').on('click', '.show-more-private-messages', function (e) {
        popovers.hide_all();
        zoom_in();
        e.preventDefault();
        e.stopPropagation();
    });
};

exports.expand = function (op_pm) {
    private_messages_open = true;
    if (op_pm.length === 1) {
        exports.rebuild_recent(op_pm[0]);
    } else if (op_pm.length !== 0) {
        // TODO: Should pass the reply-to of the thread
        exports.rebuild_recent("");
    } else {
        exports.rebuild_recent("");
    }
};

exports.update_dom_with_unread_counts = function (counts) {
    set_count(counts.private_message_count);
    counts.pm_count.each(function (count, user_ids_string) {
        // TODO: just use user_ids_string in our markup
        set_pm_conversation_count(user_ids_string, count);
    });


    unread_ui.set_count_toggle_button($("#userlist-toggle-unreadcount"),
                                      counts.private_message_count);

    unread_ui.animate_private_message_changes(get_filter_li(),
                                              counts.private_message_count);
};


exports.initialize = function () {
    pm_list.set_click_handlers();
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = pm_list;
}

