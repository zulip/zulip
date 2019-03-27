var pm_list = (function () {

var exports = {};

// This module manages the "Private Messages" section in the upper
// left corner of the app.  This was split out from stream_list.js.

function get_filter_li() {
    return $(".top_left_private_messages");
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
    var user_ids_string = people.reply_to_to_user_ids_string(conversation);
    if (!user_ids_string) {
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

exports._build_private_messages_list = function (active_conversation) {

    var private_messages = pm_conversations.recent.get();
    var display_messages = [];

    // SHIM
    if (active_conversation) {
        active_conversation = people.emails_strings_to_user_ids_string(active_conversation);
    }

    _.each(private_messages, function (private_message_obj) {
        var user_ids_string = private_message_obj.user_ids_string;
        var reply_to = people.user_ids_string_to_emails_string(user_ids_string);
        var recipients_string = people.get_recipients(user_ids_string);

        var num_unread = unread.num_unread_for_person(user_ids_string);

        var is_group = user_ids_string.indexOf(',') >= 0;

        var user_circle_class = buddy_data.get_user_circle_class(user_ids_string);

        var fraction_present;
        if (is_group) {
            user_circle_class = 'user_circle_fraction';
            fraction_present = buddy_data.huddle_fraction_present(user_ids_string);
        }

        var display_message = {
            recipients: recipients_string,
            user_ids_string: user_ids_string,
            unread: num_unread,
            is_zero: num_unread === 0,
            url: hash_util.pm_with_uri(reply_to),
            user_circle_class: user_circle_class,
            fraction_present: fraction_present,
            is_group: is_group,
        };
        display_messages.push(display_message);
    });

    var recipients_dom = templates.render('sidebar_private_message_list',
                                          {messages: display_messages});
    return recipients_dom;
};

exports.rebuild_recent = function (active_conversation) {
    stream_popover.hide_topic_popover();
    $("#private-container").remove();

    var private_li = get_filter_li();
    var private_messages_dom = exports._build_private_messages_list(
        active_conversation);

    private_li.append(private_messages_dom);

    if (active_conversation) {
        var active_li = exports.get_conversation_li(active_conversation);
        if (active_li) {
            active_li.addClass('active-sub-filter');
        }
    }

    resize.resize_stream_filters_container();
};

exports.update_private_messages = function () {
    var is_pm_filter = false;
    var pm_with = '';
    var filter = narrow_state.filter();

    if (filter) {
        var conversation = filter.operands('pm-with');
        if (conversation.length === 1) {
            pm_with = conversation[0];
        }
        if (conversation.length === 0) {
            is_pm_filter = _.contains(filter.operands('is'), "private");
        }
        // We don't support having two pm-with: operands in a search
        // (Group PMs are represented as a single pm-with operand
        // containing a list).
    }

    exports.rebuild_recent(pm_with);

    if (is_pm_filter) {
        $(".top_left_private_messages").addClass('active-filter');
    }

    if ($("#private-container").length !== 0) {
        ui.set_up_scrollbar($("#private-container"));
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
};

exports.initialize = function () {
    exports.update_private_messages();
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = pm_list;
}

window.pm_list = pm_list;
