const render_sidebar_private_message_list = require('../templates/sidebar_private_message_list.hbs');

let private_messages_open = false;

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
    const count_span = get_filter_li().find('.count');
    const value_span = count_span.find('.value');
    update_count_in_dom(count_span, value_span, count);
}

exports.get_li_for_user_ids_string = function (user_ids_string) {
    const pm_li = get_filter_li();
    const convo_li = pm_li.find("li[data-user-ids-string='" + user_ids_string + "']");
    return convo_li;
};

function set_pm_conversation_count(user_ids_string, count) {
    const pm_li = exports.get_li_for_user_ids_string(user_ids_string);
    const count_span = pm_li.find('.private_message_count');
    const value_span = count_span.find('.value');

    if (count_span.length === 0 || value_span.length === 0) {
        return;
    }

    count_span.removeClass("zero_count");
    update_count_in_dom(count_span, value_span, count);
}

function remove_expanded_private_messages() {
    stream_popover.hide_topic_popover();
    ui.get_content_element($("#private-container")).empty();
    resize.resize_stream_filters_container();
}

exports.close = function () {
    private_messages_open = false;
    remove_expanded_private_messages();
};

exports.get_active_user_ids_string = function () {
    const filter = narrow_state.filter();

    if (!filter) {
        return;
    }

    const emails = filter.operands('pm-with')[0];

    if (!emails) {
        return;
    }

    return people.emails_strings_to_user_ids_string(emails);
};

exports._build_private_messages_list = function () {

    const private_messages = pm_conversations.recent.get();
    const display_messages = [];
    const active_user_ids_string = exports.get_active_user_ids_string();

    _.each(private_messages, function (private_message_obj) {
        const user_ids_string = private_message_obj.user_ids_string;
        const reply_to = people.user_ids_string_to_emails_string(user_ids_string);
        const recipients_string = people.get_recipients(user_ids_string);

        const num_unread = unread.num_unread_for_person(user_ids_string);

        const is_group = user_ids_string.indexOf(',') >= 0;

        const is_active = user_ids_string === active_user_ids_string;

        let user_circle_class;
        let fraction_present;

        if (is_group) {
            user_circle_class = 'user_circle_fraction';
            fraction_present = buddy_data.huddle_fraction_present(user_ids_string);
        } else {
            const user_id = parseInt(user_ids_string, 10);
            user_circle_class = buddy_data.get_user_circle_class(user_id);
            const recipient_user_obj = people.get_person_from_user_id(user_id);

            if (recipient_user_obj.is_bot) {
                user_circle_class = 'user_circle_green';
            }
        }

        const display_message = {
            recipients: recipients_string,
            user_ids_string: user_ids_string,
            unread: num_unread,
            is_zero: num_unread === 0,
            is_active: is_active,
            url: hash_util.pm_with_uri(reply_to),
            user_circle_class: user_circle_class,
            fraction_present: fraction_present,
            is_group: is_group,
        };
        display_messages.push(display_message);
    });

    const recipients_dom = render_sidebar_private_message_list({
        messages: display_messages,
    });
    return recipients_dom;
};

exports.rebuild_recent = function () {
    stream_popover.hide_topic_popover();

    if (private_messages_open) {
        const rendered_pm_list = exports._build_private_messages_list();
        ui.get_content_element($("#private-container")).html(rendered_pm_list);
    }

    resize.resize_stream_filters_container();
};

exports.update_private_messages = function () {
    if (!narrow_state.active()) {
        return;
    }

    let is_pm_filter = false;
    const filter = narrow_state.filter();

    if (filter) {
        const conversation = filter.operands('pm-with');
        if (conversation.length === 0) {
            is_pm_filter = _.contains(filter.operands('is'), "private");
        }
        // We don't support having two pm-with: operands in a search
        // (Group PMs are represented as a single pm-with operand
        // containing a list).
    }

    exports.rebuild_recent();

    if (is_pm_filter) {
        $(".top_left_private_messages").addClass('active-filter');
    }
};

exports.expand = function () {
    private_messages_open = true;
    exports.rebuild_recent();
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
};

window.pm_list = exports;
